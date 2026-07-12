import joblib
import pandas as pd
model = joblib.load('../models/rf_model.joblib')
df = pd.DataFrame([{
    'text_threat_score': 0.99,
    'video_fake_score': 0.0,
    'audio_fake_score': 0.77,
    'domain_age_days': 99999,
    'is_authenticated_sender': 0
}])
print("Audio Deepfake Prediction:", model.predict_proba(df)[0][1])
