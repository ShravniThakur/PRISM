from __future__ import annotations
import torch
import torch.nn.functional as F
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification, pipeline
import numpy as np
from pathlib import Path

# Dynamically resolve PRISM root directory (3 levels up from module2)
CURRENT_DIR = Path(__file__).resolve().parent
PRISM_ROOT = CURRENT_DIR.parent.parent.parent
DEEPFAKE_MODELS_DIR = PRISM_ROOT / "DeepFakeModels"

# Global references to prevent ZeroGPU from serializing the audio model via 'self'
_AUDIO_EXTRACTOR = None
_AUDIO_MODEL = None

try:
    import spaces
except ImportError:
    class _DummySpaces:
        @staticmethod
        def GPU(func):
            return func
    spaces = _DummySpaces()

class DeepfakeScoringEngine:
    def __init__(self):
        # Force CPU to prevent Hugging Face ZeroGPU from crashing on CUDA init
        # ZeroGPU spaces strictly forbid CUDA operations outside of @spaces.GPU decorators.
        self.device = torch.device('cpu')
        print(f"DeepfakeScoringEngine running on: {self.device}")
        
        self.video_model = None
        # audio models moved to globals so ZeroGPU doesn't capture them in 'self'
        
        self._load_video_model()
        self._load_audio_model()
        
        # Must run AFTER both models load — @spaces.GPU serializes everything
        self._strip_all_parametrizations()

    def _load_video_model(self):
        print("Loading Video Deepfake Model (DeepGuard/KoreaPeter)...")
        try:
            # Map torch device to HuggingFace pipeline device string/index
            if self.device.type == "cuda":
                device_str = 0   # HF pipeline uses integer index for CUDA
            elif self.device.type == "mps":
                device_str = "mps"
            else:
                device_str = "cpu"
            import os
            import sys
            from huggingface_hub import hf_hub_download
            
            # ---------------------------------------------------------
            # HACK: Bypass transformers trust_remote_code absolute import bug
            # We explicitly download the configuration file to the local directory
            # so that pipeline_video_ms_eff_gcvit can import it directly.
            # ---------------------------------------------------------
            local_dir = os.path.dirname(os.path.abspath(__file__))
            if local_dir not in sys.path:
                sys.path.insert(0, local_dir)
                
            try:
                hf_hub_download(
                    repo_id="KoreaPeter/ms-eff-gcvit-deepfake-b5-ff-plus-plus",
                    filename="configuration_ms_eff_gcvit.py",
                    token=os.environ.get("HF_READ_TOKEN"),
                    local_dir=local_dir
                )
            except Exception as e:
                print(f"Failed to download configuration explicitly: {e}")
            
            self.video_model = pipeline(
                "video-classification",
                model="KoreaPeter/ms-eff-gcvit-deepfake-b5-ff-plus-plus",
                trust_remote_code=True,
                device=device_str,
                token=os.environ.get("HF_READ_TOKEN")
            )
            
            print("Video model loaded successfully.")
            
            # -------------------------------------------------------
            # CRITICAL: Force YOLO face detector to initialize NOW.
            # _ensure_detector() is lazy — YOLO only loads on the
            # first inference call. If we let it lazy-init inside
            # @spaces.GPU, ZeroGPU tries to serialize the newly-
            # created YOLO (which has weight_norm parametrizations)
            # and crashes. By calling it here at startup, YOLO exists
            # before ZeroGPU takes its initial tensor snapshot.
            # -------------------------------------------------------
            try:
                self.video_model._ensure_detector(conf_thres=0.5)
                print("YOLO face detector pre-initialized.")
            except Exception as yolo_e:
                print(f"YOLO pre-init failed (non-fatal): {yolo_e}")

        except Exception as e:
            print(f"Failed to load video model: {e}")

    def _strip_all_parametrizations(self):
        """
        ZeroGPU uses RPC which fails if ANY PyTorch module contains parametrizations
        (like weight_norm or spectral_norm). This globally strips both new and old
        parametrizations from all loaded models.
        """
        import torch
        import torch.nn.utils.parametrize as P
        import gc
        
        count = 0
        for obj in gc.get_objects():
            if isinstance(obj, torch.nn.Module):
                # 1. Strip new PyTorch 2.0+ parametrizations
                if P.is_parametrized(obj):
                    for attr in list(obj.parametrizations.keys()):
                        P.remove_parametrizations(obj, attr, leave_parametrized=True)
                    count += 1
                
                # 2. Strip legacy PyTorch 1.x weight_norm (Wav2Vec2 uses this!)
                if hasattr(obj, "weight_g") and hasattr(obj, "weight_v"):
                    try:
                        torch.nn.utils.remove_weight_norm(obj)
                        count += 1
                    except ValueError:
                        pass # Was not a weight_norm module or already removed
                        
        print(f"Stripped parametrizations from {count} modules. Model is ZeroGPU-compatible.")

    def _load_audio_model(self):
        print("Loading Audio Deepfake Model (Wav2Vec2)...")
        # Load Wav2Vec2 model directly from Hugging Face Hub
        model_path = "garystafford/wav2vec2-deepfake-voice-detector"
        global _AUDIO_EXTRACTOR, _AUDIO_MODEL
        try:
            _AUDIO_EXTRACTOR = AutoFeatureExtractor.from_pretrained(model_path)
            _AUDIO_MODEL = AutoModelForAudioClassification.from_pretrained(model_path)
            _AUDIO_MODEL.to(self.device)
            _AUDIO_MODEL.eval()
            print("Wav2Vec2 Weights loaded successfully.")
        except Exception as e:
            print(f"Failed to load audio model: {e}")

    @spaces.GPU
    def score_video(self, video_path: str) -> dict:
        """
        Takes a path to a raw video file.
        Uses ffmpeg to extract 5-second chunks.
        Passes them through the DeepGuard pipeline.
        Returns the overall fake probability and the timeline array.
        """
        if not video_path or not self.video_model:
            return {"overall_score": 0.0}
            
        import tempfile
        import subprocess
        import os
        import math
        
        overall = 0.0
        error_msg = None
        try:
            # 1. Get overall score directly from the full video
            full_results = self.video_model(video_path)
            for res in full_results:
                if res['label'] == 'fake':
                    overall = res['score']

            # Timeline graph data logic removed
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error evaluating video: {error_msg}")
            
        return {"overall_score": overall, "error": error_msg, "raw_results": full_results if 'full_results' in locals() else None}

    def score_audio(self, audio_array: np.ndarray, chunk_duration_sec: int = 5) -> dict:
        """
        Takes a 1D audio numpy array (16kHz), chunks it, and runs Wav2Vec2.
        Returns the filtered average fake probability and the timeline array.
        """
        global _AUDIO_EXTRACTOR, _AUDIO_MODEL
        if not _AUDIO_MODEL or audio_array is None:
            return {"overall_score": 0.0}
            
        sampling_rate = 16000
        chunk_size = sampling_rate * chunk_duration_sec
        fake_probs = []
        
        with torch.no_grad():
            for i in range(0, len(audio_array), chunk_size):
                chunk = audio_array[i:i + chunk_size]
                
                # Ignore chunks that are too short (e.g. < 1 second) to prevent garbage predictions
                if len(chunk) < sampling_rate:
                    continue
                    
                inputs = _AUDIO_EXTRACTOR(
                    chunk, 
                    sampling_rate=sampling_rate, 
                    return_tensors="pt"
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                outputs = _AUDIO_MODEL(**inputs)
                
                probs = F.softmax(outputs.logits, dim=-1)
                
                # According to garystafford model config: 0 is real, 1 is fake
                fake_prob = probs[0][1].item()
                fake_probs.append(fake_prob)
                
        # Calculate overall score removing outliers
        overall_score = 0.0
        if fake_probs:
            if len(fake_probs) > 2:
                q1 = np.percentile(fake_probs, 25)
                q3 = np.percentile(fake_probs, 75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                filtered_probs = [p for p in fake_probs if lower_bound <= p <= upper_bound]
                
                if not filtered_probs:
                    filtered_probs = fake_probs
            else:
                filtered_probs = fake_probs
                
            overall_score = sum(filtered_probs) / len(filtered_probs)
            
        return {"overall_score": overall_score}
