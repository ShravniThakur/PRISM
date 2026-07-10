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
*   **`text_hash.py` (The "Dual-Lock" System)**: Uses `TLSH` for a semantic text fingerprint. However, fuzzy hashing alone is dangerous because swapping a single URL barely changes the hash. To fix this, it actively extracts **Critical Tokens** (URLs, account numbers) and creates a strict mathematical lock on them alongside the fuzzy hash. If a hacker changes a single letter in a URL, the lock shatters and PRISM instantly flags it as Phishing!
*   **`image_hash.py`**: Calculates a `pHash` (Perceptual Hash) for images to survive compression.
*   **`video_hash.py`**: Extracts frames and calculates a temporal `pHash` fingerprint for video streams.
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
*   **`text_hash.py` (The "Dual-Lock" System)**: Uses `TLSH` for a semantic text fingerprint. However, fuzzy hashing alone is dangerous because swapping a single URL barely changes the hash. To fix this, it actively extracts **Critical Tokens** (URLs, account numbers) and creates a strict mathematical lock on them alongside the fuzzy hash. If a hacker changes a single letter in a URL, the lock shatters and PRISM instantly flags it as Phishing!
*   **`image_hash.py`**: Calculates a `pHash` (Perceptual Hash) for images to survive compression.
*   **`video_hash.py`**: Extracts frames and calculates a temporal `pHash` fingerprint for video streams.


## Generating Signatures Manually (For Swagger UI Testing)
If you are testing the API using the Swagger UI, you will need to generate cryptographic signatures locally on your machine (since Private Keys should never be sent over the internet).
Once you receive the `payload_b64` from the `/sign/prepare` endpoint, run this command in your terminal to generate the final signature:
```bash
.venv/bin/python scripts/seed_demo.py        # optional: demo entities + signed advisory
.venv/bin/uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

## Generating Signatures Manually (For Swagger UI Testing)
If you are testing the API using the Swagger UI, you will need to generate cryptographic signatures locally on your machine (since Private Keys should never be sent over the internet).
Once you receive the `payload_b64` from the `/sign/prepare` endpoint, run this command in your terminal to generate the final signature:
```bash
python3 scripts/sign_payload.py --key path_to_your_private_key.pem --payload-b64 "PASTE_PAYLOAD_B64_HERE"
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

### 🌟 The "Frictionless Verification" UX
Traditional cryptography requires the investor to upload a `.sig` signature file and a `.pem` public key alongside the document. PRISM eliminates this friction entirely.
When an investor uploads a suspicious file to `POST /verify`, they do not need to provide a signature or even select the entity from a dropdown. PRISM automatically computes the fuzzy hash of the upload and searches the *entire* `SignedAsset` database to find if any registered entity has ever signed a similar hash. If a match is found, PRISM automatically pulls the original signature and verifies it against the entity's stored public key on the backend. The investor just drags and drops the file, and PRISM does all the heavy lifting!

**Why do we still need the Signature if we are just searching the Database?**
To prevent a **Database Poisoning Attack**. If PRISM only stored fuzzy hashes without signatures, a hacker who breached the PRISM server could simply insert the fuzzy hash of their phishing video into the database and label it as "SEBI". But because PRISM requires a strict `Ed25519` cryptographic signature, even if a hacker breaches the database, they cannot forge a valid signature without SEBI's offline Private Key. 

When PRISM attempts the cryptographic math during verification, it will instantly fail and reject the forged database entry. This guarantees that no one—not even the developers of PRISM or a hacker who breaches the server—can forge a document. Only the person holding the offline Private Key has the power to authorize a hash. It's a Zero-Trust architecture at its finest!

### 🖋️ The Cryptography Analogy: Pen, Ink, and Magnifying Glass
If you are confused by how the Public Key, Private Key, and Signature interact, think of it like this:
*   **The Private Key** is a unique, magical **Pen**. It is locked inside SEBI's vault, and only they can ever hold it.
*   **The Signature** is the **Ink** left on the document after they use the pen.
*   **The Public Key** is a special **Magnifying Glass** that SEBI gives away for free to everyone in the world (stored in the PRISM database).

Because of how Asymmetric Cryptography (`Ed25519`) works, that specific Magnifying Glass (Public Key) is mathematically entangled with that specific Pen (Private Key). 
When PRISM looks at the Ink (Signature) through the Magnifying Glass (Public Key), the cryptography equations click together perfectly. The Magnifying Glass essentially says: *"I can mathematically prove, beyond a shadow of a doubt, that the specific Pen linked to me was used to write this Ink."* 

It allows PRISM to verify SEBI's identity with 100% certainty, without SEBI ever having to show PRISM their secret Pen!

Accepted uploads: raw text, `.txt`, `.eml`, `.pdf` (text is extracted),
images (`.png .jpg .webp ...`), video (`.mp4 .mov ...`). Ambiguous files can
be disambiguated with a `media_type=text|image|video` form field.

## Tuning

Thresholds live in [app/config.py](app/config.py) and are overridable via env
vars (`TEXT_TLSH_MAX_DIFF`, `IMAGE_PHASH_MAX_HAMMING`,
`VIDEO_FRAME_MAX_HAMMING`, `VIDEO_MIN_MATCH_RATIO`, `VIDEO_SAMPLE_FPS`).
Tune them against real forwarded samples before the demo.
