import librosa
import numpy as np
import torch

class AudioProcessor:
    def __init__(self, sample_rate=16000, max_duration_sec=10):
        self.sample_rate = sample_rate
        self.max_samples = sample_rate * max_duration_sec

    def extract_features(self, audio_path: str) -> np.ndarray:
        """
        Reads a wav file, resamples if necessary, and crops it 
        up to `max_samples`. Returns a 1D numpy array for HF FeatureExtractor.
        """
        if not audio_path:
            return None
            
        try:
            # Load audio using librosa, limit to max_duration_sec to prevent OOM
            max_duration = self.max_samples / self.sample_rate
            X, fs = librosa.load(audio_path, sr=self.sample_rate, duration=max_duration)
            
            return X
            
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None
