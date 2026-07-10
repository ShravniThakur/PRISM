# PRISM System Architecture

**Project Name:** PRISM - Phishing and Representation Integrity Surveillance for Markets
**Objective:** A technology-based solution to address AI-generated threats to investors and authenticate legitimate financial communications in the securities market.

---

## High-Level Architecture Overview

PRISM is designed as a **Dual-Layered System** utilizing independent microservices. This ensures separation of concerns, scalability, and allows teams to develop modules in parallel.

1.  **Microservice 1: Authentication Engine (Defensive Layer)**
2.  **Microservice 2: AI Threat Detection Engine (Offensive Layer)**
3.  **Front-End: The Web Portal (Aggregator / UI)**

---

## 1. Authentication Microservice (Layer 1)

**Purpose:** Cryptographically verify the legitimacy of communications claiming to be from official entities (SEBI, NSE, Registered Brokers).

*   **Core Tech:** Asymmetric Cryptography (Public/Private Key Infrastructure).
*   **Database:** A Key Registry containing the Public Keys of registered, verified entities.
*   **The Logic (Resilient Verification):** 
    *   To prevent "fragile UX" where normal compression (like WhatsApp forwards) breaks standard byte-sensitive hashes, PRISM uses **Semantic/Fuzzy Hashing (e.g., TLSH for text)** and **Perceptual Hashing (pHash for video/images)**.
    *   Entities use their private key to sign this perceptual/semantic hash of their asset.
    *   When an investor uploads a compressed or slightly reformatted version of the asset, the Microservice recalculates the fuzzy hash and verifies it against the Public Key.
    *   If the visual content or semantic meaning is unchanged, the verification succeeds. If a hacker alters the text meaning or splices the video (a cheapfake/deepfake), the fuzzy hash drastically changes, and the verification fails.

---

## 2. AI Threat Detection Microservice (Layer 2)

**Purpose:** Analyze unauthenticated or suspicious media for malicious intent, deepfake artifacts, and synthetic generation.

### Module 1: Text Analysis (Phishing / Manipulation)
*   **Model:** Fine-Tuned `FinBERT` (`ProsusAI/finbert`) converted into a binary sequence classifier (`SAFE=0`, `THREAT=1`).
*   **Training Data:** A custom dataset combining `Ling.csv` (phishing), `Nigerian_Fraud.csv` (advance-fee fraud), HuggingFace `FinancialPhraseBank` (safe financial news), and highly-localized synthetic Indian financial scams generated via LLM.
*   **Output:** `text_threat_score` (0.0 to 1.0) indicating manipulative, high-pressure, or fraudulent intent.

### Module 2: 

#### Vision Analysis & OCR (Video/Image Deepfakes & Cheapfakes)
*   **Pre-Processing:** 
    *   `FFmpeg` to split streams.
    *   **OCR (Optical Character Recognition):** Run `Tesseract-OCR` on OpenCV-extracted frames using Otsu's binarization to extract any text overlaid on the video (e.g., scam text added by hackers). This extracted text is passed directly into **Module 1** for intent analysis.
*   **Model:** `DeepGuard (MS-EffGCViT)` natively processes the video stream (handles its own internal YOLO face detection; no external cropping required).
*   **Output:** `video_fake_score` (0.0 to 1.0) based on spatiotemporal visual artifacts and blending inconsistencies.

#### Audio Analysis (Synthetic Voice)
*   **Model:** `wav2vec2-deepfake-voice-detector` (Hugging Face Wav2Vec2 Architecture).
*   **The Logic:** Analyzes the raw 16kHz audio waveform directly using a pre-trained Transformer architecture. Wav2Vec2 is vastly superior for production environments because it is highly robust against video compression (unlike older models which fail on WhatsApp or web-compressed `.mov`/`.mp4` audio).
*   **Output:** `audio_fake_score` (0.0 to 1.0) detecting AI-generated acoustic anomalies.

---

## 3. The Central Brain: Random Forest Scoring Engine

**Purpose:** Intelligently aggregate the outputs of all microservices into a single, highly accurate Threat Score.

*   **Model Architecture:** `scikit-learn` RandomForestClassifier (Ensemble method).
*   **Input Features (5-Dimensional Array):**
    1.  `text_threat_score` (from AI Layer)
    2.  `video_fake_score` (from AI Layer)
    3.  `audio_fake_score` (from AI Layer)
    4.  `domain_age_days` (Metadata extraction)
    5.  `is_authenticated_sender` (Binary: 0 or 1, from Auth Layer)
*   **Output:** A final probability score (0 to 100%) and a binary classification (Safe vs. Malicious).

---

## 4. Front-End Web Portal

**Tech Stack:** React + Vite (or Next.js) with Modern Fintech Aesthetics (Glassmorphism, dark slate/navy theme, neon accents).

### View A: Investor Dashboard (Public)
*   **Input Zone:** Drag-and-drop area for files (.mp4, .eml, .pdf) or a text box for suspicious URLs/messages.
*   **Processing UI:** Step-by-step loading animation showing microservice orchestration (e.g., *Verifying signature -> Extracting audio -> Analyzing intent*).
*   **Verdict Panel:** A clear Threat Gauge (Safe/Warning/Critical) followed by a detailed, explainable breakdown of the AI and Authentication scores.

### View B: Entity Portal (Admin)
*   **Key Management:** Secure login for entities (e.g., SEBI) to view or rotate their Public/Private keys.
*   **Signing Tool:** A dashboard where authorized officials can upload an official video/document, input their private key locally, and generate a cryptographic signature to attach to their public releases.

---

## System Orchestration Flow

1.  User submits an asset (and optional signature) via the **Investor Dashboard**.
2.  The Portal pings the **Authentication Microservice** to check the signature (`is_authenticated_sender`).
3.  The Portal passes the asset and the auth status to the **AI Threat Detection Microservice**.
4.  The AI Microservice runs parallel inference on the Text, Audio, and Video modules.
5.  All scores are fed into the **Random Forest Scoring Engine**.
6.  The final PRISM Threat Score is returned to the Portal and displayed to the user with actionable advice.

## Additional Features

1. **The "Viral Threat Intelligence" Dashboard (For SEBI)**
- Right now, PRISM helps the individual investor. But what if PRISM helped the government?
The Feature: If 50 different investors all upload the exact same Deepfake video to your portal within 24 hours, PRISM automatically flags this as a Viral Coordinated Attack.
- How it works: It groups the uploads by their Perceptual Hash (pHash) and generates an automated "Red Alert" on the SEBI Admin Dashboard. It tells SEBI: "A deepfake of your CEO is currently going viral on WhatsApp. Here is the file, issue a public warning immediately."

2. **The WhatsApp "Bot" Integration (Frictionless UX)**
- Investors are lazy. They don't want to open a web portal and drag-and-drop files.
The Feature: A PRISM WhatsApp Bot.
- How it works: If an investor gets a suspicious forwarded message on WhatsApp, they literally just "Forward" it to the PRISM Bot's phone number. The Bot uses the WhatsApp Business API to hit your Microservices and instantly replies: 🔴 "DANGER: 98% Threat Score. Do not click."
- The Implementation: The Twilio Sandbox (The Real Code Way)
Twilio is a massive communications API company that gives developers a completely free WhatsApp Sandbox specifically for testing and hackathons.
- How it works: You sign up for a free Twilio account, and they give you a temporary WhatsApp phone number. You link that number to a simple Python Webhook in your FastAPI backend.
The Demo: During your pitch, you can literally have the judges text that Twilio number from their personal phones, and your Python backend will instantly reply with the PRISM Threat Score. It is 100% free and works perfectly for a 6-day hackathon.

3. **"Explainable AI" (XAI) Heatmaps**
- One of the biggest criticisms of AI is that it is a "Black Box" (it just spits out a number, and you have to trust it).
- The Feature: When the Web Portal flags a video as a deepfake, it doesn't just show a score. It shows a Heatmap Image of the CEO's face, with a glowing red box over the exact pixels that were manipulated (usually the mouth or eyes).
- How to build it: In PyTorch, your engineer can use a technique called Grad-CAM (Gradient-weighted Class Activation Mapping) on the Siglip/XceptionNet model. It literally extracts the visual attention map from the neural network and returns it to the frontend.


## Drive Links
- Datasets : https://drive.google.com/drive/folders/1Pv7sMyVCeRKnZhjiNm4EINIrQklpTOPX?usp=drive_link
- DeepFakeModels : https://drive.google.com/drive/folders/1zxCBsAqQWvaaPiq-jqh1QOCB2UA8KsaH?usp=sharing
