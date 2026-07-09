# Layer 3: Central Brain (Scoring Engine)

## Overview
Layer 3 acts as the **Central Brain** of the PRISM architecture. It aggregates the individual threat signals from Layer 1 (Zero-Trust Auth) and Layer 2 (Text, Video, and Audio AI models) into a definitive, final threat verdict using a `RandomForestClassifier`.

By looking at the complete holistic picture (e.g., merging a slightly suspicious text score with a brand-new domain and an unauthenticated sender), the Central Brain achieves much higher accuracy than any single microservice operating in a silo.

## Features Extracted

The model takes a 5-dimensional array as input:

1. **`text_threat_score`** (float, 0.0-1.0): From Layer 2 Module 1 (FinBERT sequence classifier).
2. **`video_fake_score`** (float, 0.0-1.0): From Layer 2 Module 2 (DeepGuard MS-EffGCViT).
3. **`audio_fake_score`** (float, 0.0-1.0): From Layer 2 Module 2 (Wav2Vec2 Voice Detector).
4. **`domain_age_days`** (int): Dynamically calculated using a live `WHOIS` lookup against the sender's email domain or suspicious URLs found in the text. Scammers heavily rely on freshly registered domains (less than 30 days old).
5. **`is_authenticated_sender`** (int, 0 or 1): The cryptographic signature status from Layer 1.

## Model Training (Synthetic Data)
Because live datasets containing perfectly annotated scores across all 5 of these specific dimensions are rare, we generate a synthetic dataset mapping realistic attack scenarios:
- **Phishing Link / Zero-Day Domain**: High text threat + New domain age (Malicious)
- **Blatant Deepfake**: High video/audio anomaly (Malicious)
- **Hacked Account Takeover**: Authenticated sender + High text threat + New domain link (Malicious)
- **Legitimate Broadcast**: Authenticated sender + Old domain + Low threat signals (Safe)

Run `python scripts/generate_dataset.py` to create this dataset (`data/synthetic_rf_data.csv`).
Run `python scripts/train_rf.py` to train the model.

## API Endpoints
This module is exposed as its own independent FastAPI microservice.

Visit the Swagger UI at `/docs` to test the `/brain/score` endpoint interactively!
