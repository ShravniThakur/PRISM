# Layer 2: AI Threat Detection Engine

## Overview
Layer 2 is the core AI microservice of PRISM. It hosts the machine learning models that analyze the content of the message:
1. **Module 1 (Text Analysis):** A fine-tuned `FinBERT` sequence classifier that detects manipulative, high-pressure, or fraudulent language. It also includes a custom URL analyzer that checks for typo-squatted Indian financial domains.
2. **Module 2 (Media Analysis):** 
   - Uses `DeepGuard (MS-EffGCViT)` to detect spatiotemporal anomalies in videos (Deepfakes/Cheapfakes).
   - Uses `Wav2Vec2` to detect AI-generated synthetic voice audio.
   - Uses `Tesseract-OCR` to extract any scam text overlaid on the media.

## API Endpoints
This entire layer is exposed as a unified FastAPI microservice.

From the Swagger UI (`/docs`), you can interactively test:
- `POST /analyze/text` (Submit raw text to FinBERT)
- `POST /analyze/media` (Upload a `.mp4` or `.wav` to test the deepfake models)
