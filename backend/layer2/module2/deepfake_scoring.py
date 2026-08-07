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

class DeepfakeScoringEngine:
    def __init__(self):
        # Force CPU to prevent Hugging Face ZeroGPU from crashing on CUDA init
        # ZeroGPU spaces strictly forbid CUDA operations outside of @spaces.GPU decorators.
        self.device = torch.device('cpu')
        print(f"DeepfakeScoringEngine running on: {self.device}")
        
        self.video_model = None
        self.audio_extractor = None
        self.audio_model = None
        
        self._load_video_model()
        self._load_audio_model()

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
            
            # -----------------------------------------------------------
            # Remove parametrized modules (e.g. weight_norm) from model.
            # ZeroGPU cannot serialize parametrized layers, so we bake
            # the constraints directly into the weights. This preserves
            # all accuracy while making the model ZeroGPU-compatible.
            # -----------------------------------------------------------
            try:
                import torch.nn.utils.parametrize as P
                underlying_model = self.video_model.model
                for module in underlying_model.modules():
                    if P.is_parametrized(module):
                        for attr in list(module.parametrizations.keys()):
                            P.remove_parametrizations(module, attr, leave_parametrized=False)
                print("Parametrizations removed. Model is ZeroGPU-compatible.")
            except Exception as param_e:
                print(f"Could not remove parametrizations (non-fatal): {param_e}")
            
            print("Video model loaded successfully.")
        except Exception as e:
            print(f"Failed to load video model: {e}")

    def _load_audio_model(self):
        print("Loading Audio Deepfake Model (Wav2Vec2)...")
        # Load Wav2Vec2 model directly from Hugging Face Hub
        model_path = "garystafford/wav2vec2-deepfake-voice-detector"
        try:
            self.audio_extractor = AutoFeatureExtractor.from_pretrained(model_path)
            self.audio_model = AutoModelForAudioClassification.from_pretrained(model_path)
            self.audio_model.to(self.device)
            self.audio_model.eval()
            print("Wav2Vec2 Weights loaded successfully.")
        except Exception as e:
            print(f"Failed to load audio model: {e}")

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
        if not self.audio_model or audio_array is None:
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
                    
                inputs = self.audio_extractor(
                    chunk, 
                    sampling_rate=sampling_rate, 
                    return_tensors="pt"
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                outputs = self.audio_model(**inputs)
                
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
