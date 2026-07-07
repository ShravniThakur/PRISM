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
*   **Model:** Fine-Tuned Llama 3 (8B) or Mistral (7B).
*   **Training Data:** A custom dataset combining the Enron Phishing dataset, HuggingFace Financial PhraseBank, and synthetic financial scams generated via LLM.
*   **Output:** `text_threat_score` (0.0 to 1.0) indicating manipulative, high-pressure, or fraudulent intent.

### Module 2: Vision Analysis & OCR (Video/Image Deepfakes & Cheapfakes)
*   **Pre-Processing:** 
    *   `FFmpeg` to split streams.
    *   `OpenCV` to extract frames.
    *   **OCR (Optical Character Recognition):** Run `Tesseract-OCR` or `EasyOCR` on the frames to extract any text overlaid on the video (e.g., scam text added by hackers). This extracted text is passed directly into **Module 1** for intent analysis.
    *   Face-cropper to isolate the subject.
*   **Model:** `video_deepfake_siglip.safetensors` (Hugging Face) OR `XceptionNet` (FaceForensics++ baseline).
*   **Output:** `video_fake_score` (0.0 to 1.0) based on visual artifacts and blending inconsistencies.

### Module 3: Audio Analysis (Synthetic Voice)
*   **Model:** `audio_deepfake_rawnet2.pth` (ASVspoof 2021 Baseline).
*   **The Logic:** Analyzes the raw `.wav` or `.flac` waveform directly using Mel-scale sinc filters, completely bypassing the need for manual spectrogram extraction.
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
