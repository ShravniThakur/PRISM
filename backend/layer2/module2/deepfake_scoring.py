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
        # Check if MPS is available for GPU acceleration on Mac
        self.device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
        print(f"DeepfakeScoringEngine running on: {self.device}")
        
        self.video_model = None
        self.audio_extractor = None
        self.audio_model = None
        
        self._load_video_model()
        self._load_audio_model()

    def _load_video_model(self):
        print("Loading Video Deepfake Model (DeepGuard/KoreaPeter)...")
        try:
            device_str = "mps" if self.device.type == "mps" else "cpu"
            self.video_model = pipeline(
                "video-classification",
                model="KoreaPeter/ms-eff-gcvit-deepfake-b5-ff-plus-plus",
                trust_remote_code=True,
                device=device_str,
                model_kwargs={"cache_dir": str(DEEPFAKE_MODELS_DIR)}
            )
            print("Video model loaded successfully.")
        except Exception as e:
            print(f"Failed to load video model: {e}")

    def _load_audio_model(self):
        print("Loading Audio Deepfake Model (Wav2Vec2)...")
        # Load local Wav2Vec2 model from DeepFakeModels folder
        model_path = str(DEEPFAKE_MODELS_DIR / "wav2vec2-deepfake-voice-detector")
        try:
            self.audio_extractor = AutoFeatureExtractor.from_pretrained(model_path)
            self.audio_model = AutoModelForAudioClassification.from_pretrained(model_path)
            self.audio_model.to(self.device)
            self.audio_model.eval()
            print("Wav2Vec2 Weights loaded successfully.")
        except Exception as e:
            print(f"Failed to load audio model: {e}")

    def score_video(self, video_path: str) -> float:
        """
        Takes a path to a raw video file.
        Passes it through the DeepGuard pipeline.
        Returns the fake probability.
        """
        if not video_path or not self.video_model:
            return 0.0
            
        try:
            results = self.video_model(video_path)
            # results format: [{'label': 'fake', 'score': 0.9972}, {'label': 'real', 'score': 0.0028}]
            # Find the score for 'fake'
            for res in results:
                if res['label'] == 'fake':
                    return res['score']
        except Exception as e:
            print(f"Error scoring video: {e}")
            
        return 0.0

    def score_audio(self, audio_array: np.ndarray, chunk_duration_sec: int = 5) -> float:
        """
        Takes a 1D audio numpy array (16kHz), chunks it, and runs Wav2Vec2.
        Returns the filtered average fake probability.
        """
        if not self.audio_model or audio_array is None:
            return 0.0
            
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
                
        # Remove outliers and average the remaining probabilities
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
                
            return sum(filtered_probs) / len(filtered_probs)
        return 0.0
