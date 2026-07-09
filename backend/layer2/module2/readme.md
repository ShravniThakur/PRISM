# PRISM Layer 2: Deepfake ML Infrastructure

Module 2 contains the core machine learning inference pipeline for analyzing videos, splitting the audio/visual streams, and passing them through state-of-the-art Deepfake detection transformers.

## 🚀 The Pipeline
1. **Media Ingest**: Uses `ffmpeg` to isolate the 16kHz audio stream from the video.
2. **Vision Processing**: Uses **Tesseract OCR** on the video to extract any visible on-screen text.
3. **Deepfake Scoring**: 
   - **Video**: Passes the raw video through **DeepGuard (MS-EffGCViT)** (`KoreaPeter/ms-eff-gcvit-deepfake-b5-ff-plus-plus`), which natively handles internal spatiotemporal face tracking without requiring an external cropper like MTCNN.
   - **Audio**: Passes 16kHz audio waveforms through **Wav2Vec2** (`garystafford/wav2vec2-deepfake-voice-detector`).

## 📂 File Architecture
Here is exactly what each Python file in this module is responsible for:

*   **`media_ingest.py`**: The entry point. It takes raw uploaded video files and uses `ffmpeg` to isolate a `16kHz .wav` audio stream.
*   **`vision_processing.py`**: Runs **Tesseract OCR** to grab text from the video frame using Otsu's binarization.
*   **`audio_processing.py`**: Loads the `.wav` file into memory using `librosa` and formats it into a raw 1D numpy array for the HuggingFace transformer.
*   **`deepfake_scoring.py`**: The heavy lifter. Loads the offline HuggingFace models (`DeepGuard` and `Wav2Vec2`) into your Mac's MPS GPU memory, runs the tensors through the neural networks, and returns the mathematically accurate Fake/Real probabilities.
*   **`router.py`**: The FastAPI endpoints. It exposes the pipeline to the internet so the React frontend can upload files and get JSON responses back. 
*   **`test_pipeline.py`**: A standalone developer script you can run in your terminal to process a local `.mov` file without needing to boot up a web server.


## 🧪 How to Test

You can manually test the pipeline by placing a `.mov` or `.mp4` file into the `backend/layer2/module2/test/` folder and updating `test_pipeline.py` to point to your file.

1. Navigate to the `module2` folder:
```bash
cd backend/layer2/module2
```

2. Run the test pipeline:
```bash
python test_pipeline.py
```

## 📊 Interpreting the Output

When you run the script, it will output a **Video Fake Score** and an **Audio Fake Score** between `0.0` and `1.0`.

*   **0.0 (0%)** = The model is highly confident the media is pristine, un-altered, and **Real**.
*   **1.0 (100%)** = The model is highly confident the media is synthesized, manipulated, or AI-generated (**Fake**).

**Common Edge Cases:**
*   **Face-Swaps**: You will often see extremely high Video scores (`> 0.90`) but very low Audio scores (`< 0.10`). This indicates the hacker manipulated the video but left the original human audio track intact.
*   **Compression Sensitivity**: Pre-trained vision models are highly sensitive to video compression. A 100% real iPhone video sent over WhatsApp might score a `0.60` Video Fake score simply because the AI detects the compression artifacts.

## Sources 
- https://huggingface.co/KoreaPeter/ms-eff-gcvit-deepfake-b5-ff-plus-plus
- https://huggingface.co/garystafford/wav2vec2-deepfake-voice-detector/tree/main
