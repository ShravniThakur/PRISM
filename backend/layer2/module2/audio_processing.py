from __future__ import annotations
import librosa
import numpy as np
import torch
from transformers import pipeline

class AudioProcessor:
    def __init__(self, sample_rate=16000, max_duration_sec=10):
        self.sample_rate = sample_rate
        self.max_samples = sample_rate * max_duration_sec
        # Use Whisper Tiny (100% free, local, open-source model)
        # Force CPU to prevent ZeroGPU interception crashes
        self.stt_pipeline = pipeline("automatic-speech-recognition", model="openai/whisper-tiny", device="cpu")

    def extract_features(self, audio_path: str) -> np.ndarray:
        """
        Reads a wav file, crops it up to `max_samples`. 
        Returns a 1D numpy array for HF FeatureExtractor.
        """
        if not audio_path:
            return None
            
        try:
            import soundfile as sf
            X, fs = sf.read(audio_path)
            
            # Check for pure silence or extreme quietness (< -60 dBFS approx)
            if np.max(np.abs(X)) < 0.001:
                print(f"Audio file {audio_path} is considered silent. Skipping.")
                return None
            
            # Limit to max_duration_sec to prevent OOM
            if len(X) > self.max_samples:
                X = X[:self.max_samples]
                
            return X
            
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribes the audio file using the local Whisper model.
        """
        if not audio_path:
            return ""
            
        # Check for silence before transcription to prevent Whisper from hallucinating
        try:
            import soundfile as sf
            X, fs = sf.read(audio_path)
            if np.max(np.abs(X)) < 0.001:
                print(f"Audio file {audio_path} is silent. Skipping transcription.")
                return ""
        except Exception as e:
            print(f"Error checking audio silence: {e}")
        
        try:
            print(f"Transcribing audio: {audio_path}")
            # Whisper handles internal resampling and duration via the pipeline
            result = self.stt_pipeline(audio_path, chunk_length_s=30, return_timestamps=False)
            return result.get("text", "").strip()
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return ""
