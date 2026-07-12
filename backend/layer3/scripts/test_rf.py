import joblib
import pandas as pd

model = joblib.load('../models/rf_model.joblib')

def test(text, video, audio, domain, auth):
    df = pd.DataFrame([{
        'text_threat_score': text,
        'video_fake_score': video,
        'audio_fake_score': audio,
        'domain_age_days': domain,
        'is_authenticated_sender': auth
    }])
    prob = model.predict_proba(df)[0][1]
    print(f"Text={text}, Vid={video}, Aud={audio}, Dom={domain}, Auth={auth} -> {prob:.2f}")

test(0.99, 1.0, 0.36, 99999, 0)
test(0.99, 1.0, 0.86, 99999, 0) # High audio
test(0.99, 1.0, 0.36, 10, 0)    # Malicious domain
test(0.20, 0.1, 0.10, 99999, 1) # Safe
