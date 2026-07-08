import torch
import torch.nn.functional as F
from transformers import AutoImageProcessor, AutoModelForImageClassification
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
import numpy as np

class DeepfakeScoringEngine:
    def __init__(self):
        # Check if MPS is available for GPU acceleration on Mac
        self.device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
        print(f"DeepfakeScoringEngine running on: {self.device}")
        
        self.video_processor = None
        self.video_model = None
        self.audio_extractor = None
        self.audio_model = None
        
        self._load_video_model()
        self._load_audio_model()

    def _load_video_model(self):
        print("Loading Video Deepfake Model (SigLIP)...")
        # Load the SigLIP vision model
        # Using a widely available pre-trained deepfake classification model from HF
        model_name = "prithivMLmods/deepfake-detector-model-v1"
        try:
            self.video_processor = AutoImageProcessor.from_pretrained(model_name)
            self.video_model = AutoModelForImageClassification.from_pretrained(model_name)
            self.video_model.to(self.device)
            self.video_model.eval()
        except Exception as e:
            print(f"Failed to load video model: {e}")

    def _load_audio_model(self):
        print("Loading Audio Deepfake Model (Wav2Vec2)...")
        # Load local Wav2Vec2 model from DeepFakeModels folder
        # garystafford/wav2vec2-deepfake-voice-detector
        model_path = "/Users/shravnithakur/Desktop/PRISM/DeepFakeModels/wav2vec2-deepfake-voice-detector"
        try:
            self.audio_extractor = AutoFeatureExtractor.from_pretrained(model_path)
            self.audio_model = AutoModelForAudioClassification.from_pretrained(model_path)
            self.audio_model.to(self.device)
            self.audio_model.eval()
            print("Wav2Vec2 Weights loaded successfully.")
        except Exception as e:
            print(f"Failed to load audio model: {e}")

    def score_video_faces(self, face_tensors: list) -> float:
        """
        Takes a list of face tensors (already cropped by MTCNN).
        Passes them through the SigLIP model to get fake probabilities.
        Returns the highest fake probability found in the video.
        """
        if not face_tensors or not self.video_model:
            return 0.0
            
        fake_probs = []
        with torch.no_grad():
            for face_tensor in face_tensors:
                # MTCNN returns tensors (C, H, W). We need to convert back to format expected by HF processor
                # HF processor usually expects PIL images or numpy arrays in (H, W, C)
                # Ensure it is moved to CPU before converting to numpy
                face_np = face_tensor.permute(1, 2, 0).cpu().numpy()
                
                # Normalize back to 0-255 range if MTCNN scaled it to -1 to 1
                if face_np.min() < 0:
                    face_np = ((face_np + 1) * 127.5).astype(np.uint8)
                else:
                    face_np = face_np.astype(np.uint8)
                
                inputs = self.video_processor(images=face_np, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                outputs = self.video_model(**inputs)
                
                # Apply softmax to get probabilities
                probs = F.softmax(outputs.logits, dim=-1)
                
                # According to SigLIP config: 0 is Fake, 1 is Real
                fake_prob = probs[0][0].item() 
                fake_probs.append(fake_prob)
                
        # Return the maximum fake probability found across all frames (better than average to catch splices)
        if fake_probs:
            return max(fake_probs)
        return 0.0

    def score_audio(self, audio_array: np.ndarray) -> float:
        """
        Takes a 1D audio numpy array (16kHz) and runs Wav2Vec2.
        """
        if not self.audio_model or audio_array is None:
            return 0.0
            
        with torch.no_grad():
            # Pass raw waveform through feature extractor
            inputs = self.audio_extractor(
                audio_array, 
                sampling_rate=16000, 
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            outputs = self.audio_model(**inputs)
            
            # The Wav2Vec2 model outputs logits
            probs = F.softmax(outputs.logits, dim=-1)
            
            # According to garystafford model config: 0 is real, 1 is fake
            fake_prob = probs[0][1].item()
            return fake_prob
