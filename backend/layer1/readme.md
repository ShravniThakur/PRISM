# PRISM Layer 1 — Authentication Engine

Cryptographically verifies that a communication really came from a registered
entity (SEBI, NSE, brokers), even after WhatsApp-style compression.

**How it works (two checks):** entities sign the *fuzzy hash* of their asset
(TLSH for text, pHash for images, per-frame pHash for video) with an Ed25519
private key. On verification, PRISM recomputes the fuzzy hash of the upload,
finds the closest signed original in the registry (similarity check), then
verifies that record's signature against the entity's registered public key
(signature check). Both must pass for `is_authenticated_sender = 1`.

For text, fuzzy distance alone is not enough — swapping a single URL barely
moves the TLSH hash. Critical tokens (URLs, account-number-length digit runs)
are therefore extracted and signed alongside the hash; an upload that
introduces or alters any critical token fails verification even when the
prose is near-identical, and `/verify` flags it as suspected tampering.
Private keys never touch the server — signing happens client-side
(see `scripts/sign_payload.py`).
## 📂 File Architecture
Here is exactly what every file and folder inside `app/` is doing:

### ⚙️ The Core Server
*   **`main.py`**: The entry point. It boots up the FastAPI web server and mounts all the API routes.
*   **`config.py`**: The "Control Center". Stores sensitivity thresholds (e.g., how different a video's pixels can be before it's flagged as a Deepfake rather than WhatsApp compression).

### 🗄️ The Database Layer
*   **`db.py`**: Connects to a local SQLite database to safely store the registry of trusted entities.
*   **`models.py`**: Defines the database tables using SQLAlchemy (`Entity` and `SignedAsset`).
*   **`schemas.py`**: Pydantic models that strictly validate all incoming JSON data to prevent malformed requests.

### 🌐 The API Endpoints (`routers/` folder)
*   **`entities.py`**: Endpoints to register trusted organizations and store their Public Keys.
*   **`sign.py`**: Endpoints for entities to publish a new video (calculates fingerprint and stores cryptographic signature).
*   **`verify.py`**: **The core verification endpoint.** Takes a suspicious forwarded video, calculates its fingerprint, and checks the database for a valid signature.

### 🔐 The Cryptography (`crypto/` folder)
*   **`keys.py`**: Uses `Ed25519` asymmetric cryptography to generate Public and Private key pairs.
*   **`signing.py`**: The mathematical logic to verify a cryptographic signature against a public key.

### 🧠 The Fuzzy Hashers (`hashing/` folder)
*   **`text_hash.py`**: Uses `TLSH` for a semantic text fingerprint and actively extracts **Critical Tokens** (URLs, account numbers) to catch phishing links.
*   **`image_hash.py`**: Calculates a `pHash` (Perceptual Hash) for images to survive compression.
*   **`video_hash.py`**: Extracts frames and calculates a temporal `pHash` fingerprint for video streams.

## Setup

```bash
cd backend/layer1
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python scripts/seed_demo.py        # optional: demo entities + signed advisory
.venv/bin/uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

## Test

```bash
.venv/bin/pytest -q
```

## API

| Endpoint | Purpose |
|---|---|
| `POST /entities` | Register entity; generates a keypair (private key returned **once**) or accepts a bring-your-own `public_key_pem` |
| `GET /entities/{id}` | Entity info + public key history |
| `POST /entities/{id}/keys/rotate` | Revoke active key, issue a new one (old assets keep verifying) |
| `POST /sign/prepare` | Upload asset (`file` or `text` form field) → canonical payload to sign locally |
| `POST /sign/submit` | Store the signed record after verifying the signature |
| `POST /verify` | Investor check → `is_authenticated_sender` (0/1), matched entity, similarity, detail |

`POST /verify` output feeds the Random Forest scoring engine (the
`is_authenticated_sender` feature) and the portal's verdict panel.

Accepted uploads: raw text, `.txt`, `.eml`, `.pdf` (text is extracted),
images (`.png .jpg .webp ...`), video (`.mp4 .mov ...`). Ambiguous files can
be disambiguated with a `media_type=text|image|video` form field.

## End-to-end demo (curl)

```bash
# 1. Register an entity (save the private key!)
curl -s -X POST localhost:8000/entities -H 'content-type: application/json' \
  -d '{"name": "SEBI", "type": "regulator"}' > entity.json
python3 -c "import json;open('sebi.pem','w').write(json.load(open('entity.json'))['private_key_pem'])"

# 2. Prepare: get the payload to sign
curl -s -X POST localhost:8000/sign/prepare -F 'text=<official announcement text>' > prep.json

# 3. Sign locally (private key never leaves your machine)
SIG=$(python3 scripts/sign_payload.py --key sebi.pem \
      --payload-b64 "$(python3 -c "import json;print(json.load(open('prep.json'))['payload_b64'])")")

# 4. Submit the signed record
curl -s -X POST localhost:8000/sign/submit -H 'content-type: application/json' \
  -d "{\"entity_id\": \"$(python3 -c "import json;print(json.load(open('entity.json'))['id'])")\",
       \"payload_b64\": $(python3 -c "import json;print(json.dumps(json.load(open('prep.json'))['payload_b64']))"),
       \"signature_b64\": \"$SIG\", \"title\": \"Official announcement\"}"

# 5. Verify a forwarded copy
curl -s -X POST localhost:8000/verify -F 'text=<the forwarded version>'
```

## Tuning

Thresholds live in [app/config.py](app/config.py) and are overridable via env
vars (`TEXT_TLSH_MAX_DIFF`, `IMAGE_PHASH_MAX_HAMMING`,
`VIDEO_FRAME_MAX_HAMMING`, `VIDEO_MIN_MATCH_RATIO`, `VIDEO_SAMPLE_FPS`).
Tune them against real forwarded samples before the demo.
