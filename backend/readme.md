# PRISM Backend

Welcome to the PRISM Backend. This backend is built using a strict **Microservices Architecture** to ensure that high-CPU machine learning workloads do not block the cryptography engine or the central brain.

## 📦 Requirements & Setup
We have consolidated all dependencies for the entire backend into a single `requirements.txt` file located in this directory.

To set up your environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 🚀 Running the Microservices
The backend consists of 3 completely decoupled FastAPI applications. You can run them independently in separate terminal windows (ensure your `.venv` is activated in each!).

### Layer 1: Zero-Trust Authentication
Handles cryptographic signature verification (`pHash`, `TLSH`) to prove whether a message genuinely came from a verified financial institution.
```bash
# From the backend/ directory:
python -m uvicorn layer1.app.main:app --port 8000 --reload
```
*Swagger UI:* [http://localhost:8000/docs](http://localhost:8000/docs)

### Layer 2: AI Threat Detection
The heavy-lifting AI layer. It loads the `FinBERT` sequence classifier for text, the `DeepGuard` spatiotemporal model for video deepfakes, and `Wav2Vec2` for audio deepfakes.
*(Note: Takes 10-15 seconds to boot up as it loads 2GB+ of tensor weights into memory).*
```bash
# From the backend/ directory:
python -m uvicorn layer2.main:app --port 8001
```
*Swagger UI:* [http://localhost:8001/docs](http://localhost:8001/docs)

### Layer 3: Central Brain (Scoring Engine)
Takes the outputs from Layer 1 and Layer 2, performs a dynamic WHOIS lookup for domain age, and runs the entire 5-dimensional vector through a trained Random Forest to output a final threat verdict.
```bash
# From the backend/ directory:
python -m uvicorn layer3.main:app --port 8002 --reload
```
*Swagger UI:* [http://localhost:8002/docs](http://localhost:8002/docs)

## 🧪 How to Test Layer 1 (Zero-Trust Auth) via Swagger UI

Since Layer 1 uses offline cryptographic signatures to ensure zero-trust security, you cannot just click "Execute" on the `/sign/submit` endpoint without generating a signature first. Follow these steps to test it manually from your browser:

1. **Register an Entity & Save the Private Key**
   - Go to `http://localhost:8000/docs` and open `POST /entities`.
   - Click **Try it out**. In the Request body, enter: `{"name": "SEBI", "type": "regulator"}`
   - Click **Execute**. 
   - **IMPORTANT:** Look at the response body. Copy the entire string inside `"private_key_pem"` (including the `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` parts). 
   - Open your IDE or a text editor, create a new file inside the `backend/layer1/` folder, name it exactly `sebi.pem`, and paste the key you just copied into it. Save the file.
   - Also, copy the `"id"` string from that same JSON response (you'll need this ID later).

2. **Prepare the Payload**
   - Open `POST /sign/prepare`.
   - Click **Try it out**. In the `text` field, type a fake official announcement that is at least a few sentences long to trigger the fuzzy hashing algorithm, and include a URL (e.g., `"Official SEBI advisory: Do not share your OTPs, passwords, or PIN numbers with anyone claiming to be from the stock exchange. We will never call you asking for this information. Verify your KYC only at https://sebi.gov.in."`).
   - Click **Execute**.
   - Copy the huge string inside `"payload_b64"` from the response.

3. **Generate the Offline Signature (Terminal)**
   - Open your terminal and navigate to the `layer1` directory where you just saved the `sebi.pem` file. Run the offline signing script:
   ```bash
   cd backend/layer1
   source ../.venv/bin/activate
   python scripts/sign_payload.py --key sebi.pem --payload-b64 "PASTE_THE_HUGE_PAYLOAD_STRING_HERE"
   ```
   - The script will mathematically sign the hash using your local key and output your cryptographic signature (a long base64 string). Copy it.

4. **Submit the Signed Record**
   - Go back to Swagger and open `POST /sign/submit`.
   - Click **Try it out**. Enter the JSON:
   ```json
   {
     "entity_id": "PASTE_THE_ID_FROM_STEP_1",
     "payload_b64": "PASTE_THE_HUGE_PAYLOAD_STRING_FROM_STEP_2",
     "signature_b64": "PASTE_THE_SIGNATURE_FROM_STEP_3",
     "title": "Official announcement"
   }
   ```
   - Click **Execute**. The record is now permanently secured in the database!

5. **Verify a Forwarded Message**
   - Open `POST /verify`.
   - Click **Try it out**. In the `text` field, paste the exact same text you used in Step 2.
   - Click **Execute**. You will see `is_authenticated_sender: 1` if it matches perfectly!

## 🧪 How to Test Layer 2 (AI Threat Engine) via Swagger UI

1. **Test Text Analysis (FinBERT)**
   - Go to `http://localhost:8001/docs` and open `POST /analyze/text`.
   - Click **Try it out**. In the `text` string, type a realistic phishing attempt (e.g., `"Dear Customer, your DEMAT account KYC has expired. Your trading account will be blocked in 24 hours. Click here immediately to update your PAN and Aadhar to prevent account closure: http://sebii.gov.in/login"`).
   - Click **Execute** and review the `threat_score_text` (closer to 1.0 means highly suspicious).

2. **Test Media Analysis (DeepGuard & Wav2Vec2)**
   - Open `POST /analyze/media`.
   - Click **Try it out**. Click **Choose File** and upload a test `.mp4` video or `.wav` audio file.
   - Click **Execute**. The server will take a few moments to run inference and will return a `video_fake_score` and `audio_fake_score`.

## 🧪 How to Test Layer 3 (Central Brain) via Swagger UI

Layer 3 requires the outputs of Layer 1 and Layer 2 to make a final decision. You can manually feed it mock data to see how the Random Forest reacts.

1. **Test the Central Brain**
   - Go to `http://localhost:8002/docs` and open `POST /brain/score`.
   - Click **Try it out**. Enter a JSON payload that simulates a hacked account (authenticated sender, but highly suspicious content and a brand new domain):
   ```json
   {
     "text_score": 0.95,
     "video_score": 0.0,
     "audio_score": 0.0,
     "domain": "sebi-kyc-update.com",
     "is_authenticated_sender": 1
   }
   ```
   - Click **Execute**. The Random Forest should flag this as a severe threat, despite the `is_authenticated_sender` being 1, because the text is malicious and the domain is brand new!
