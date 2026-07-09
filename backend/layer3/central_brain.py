import os
import joblib
import pandas as pd
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("CentralBrain")

class CentralBrain:
    def __init__(self, model_path: str = None):
        if model_path is None:
            # Default to the models directory relative to this script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, 'models', 'rf_model.joblib')
            
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}. Please train the model first.")
            
        self.model = joblib.load(model_path)
        log.info("Central Brain (Random Forest) loaded successfully.")

    def calculate_final_threat(
        self, 
        text_score: float, 
        video_score: float, 
        audio_score: float, 
        domain_age_days: int, 
        is_authenticated_sender: int
    ) -> Dict[str, Any]:
        """
        Takes raw features from all PRISM microservices and predicts final threat.
        
        Args:
            text_score (float): Module 1 score (0.0 to 1.0)
            video_score (float): Module 2 Vision score (0.0 to 1.0)
            audio_score (float): Module 2 Audio score (0.0 to 1.0)
            domain_age_days (int): Extracted from WHOIS (0+)
            is_authenticated_sender (int): 1 if Safe, 0 if Unauthenticated/Spoofed
            
        Returns:
            dict containing:
                - threat_probability (float, 0-100)
                - classification (str, "Safe" or "Malicious")
        """
        # Format as pandas DataFrame to match training feature names
        features = pd.DataFrame([{
            'text_threat_score': text_score,
            'video_fake_score': video_score,
            'audio_fake_score': audio_score,
            'domain_age_days': domain_age_days,
            'is_authenticated_sender': is_authenticated_sender
        }])
        
        # Predict probability of class 1 (Malicious)
        prob = self.model.predict_proba(features)[0][1]
        
        # Binary prediction (threshold 0.5)
        pred = self.model.predict(features)[0]
        
        return {
            "threat_probability": round(prob * 100, 2),
            "classification": "Malicious" if pred == 1 else "Safe",
            "features_used": {
                "text_score": text_score,
                "video_score": video_score,
                "audio_score": audio_score,
                "domain_age": domain_age_days,
                "is_auth": is_authenticated_sender
            }
        }

if __name__ == "__main__":
    # Smoke test
    try:
        brain = CentralBrain()
        
        print("\n--- TEST CASE 1: Blatant Deepfake ---")
        res1 = brain.calculate_final_threat(
            text_score=0.9, video_score=0.95, audio_score=0.98, domain_age_days=2, is_authenticated_sender=0
        )
        print(f"Result: {res1['classification']} ({res1['threat_probability']}%)")
        
        print("\n--- TEST CASE 2: Safe Authenticated Broadcast ---")
        res2 = brain.calculate_final_threat(
            text_score=0.1, video_score=0.0, audio_score=0.0, domain_age_days=1500, is_authenticated_sender=1
        )
        print(f"Result: {res2['classification']} ({res2['threat_probability']}%)")
        
        print("\n--- TEST CASE 3: Phishing Link from Hacked Account ---")
        res3 = brain.calculate_final_threat(
            text_score=0.99, video_score=0.0, audio_score=0.0, domain_age_days=5, is_authenticated_sender=1
        )
        print(f"Result: {res3['classification']} ({res3['threat_probability']}%)")
        
    except FileNotFoundError as e:
        print(e)
