import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import shutil

from layer2.module2.media_ingest import MediaIngestor
from layer2.module2.vision_processing import VisionProcessor
from layer2.module2.audio_processing import AudioProcessor
from layer2.module2.deepfake_scoring import DeepfakeScoringEngine

router = APIRouter(prefix="/analyze", tags=["Media Deepfake Detection"])

# Initialize all components
ingestor = MediaIngestor()
vision_processor = VisionProcessor()
audio_processor = AudioProcessor()
scoring_engine = DeepfakeScoringEngine()

@router.post("/media")
async def analyze_media_endpoint(file: UploadFile = File(...)):
    """
    Receives an uploaded media file (.mp4, .wav).
    1. Splits video and audio.
    2. Extracts faces and OCR text.
    3. Runs Deepfake inference on both channels.
    """
    # 1. Save the uploaded file temporarily
    file_location = os.path.join(ingestor.upload_dir, file.filename)
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    try:
        # 2. Split Media
        media_paths = ingestor.process_upload(file_location)
        
        vision_score = 0.0
        audio_score = 0.0
        extracted_text = ""
        
        # 3. Vision Pipeline
        if media_paths.get("has_video"):
            print("Processing Vision Pipeline...")
            vision_data = vision_processor.extract_features(media_paths["video_only"])
            extracted_text = vision_data["ocr_text"]
            face_frames = vision_data["face_frames"]
            
            # Score the faces
            vision_score = scoring_engine.score_video_faces(face_frames)
            
        # 4. Audio Pipeline
        if media_paths.get("has_audio"):
            print("Processing Audio Pipeline...")
            audio_tensor = audio_processor.extract_features(media_paths["audio_only"])
            
            # Score the audio
            audio_score = scoring_engine.score_audio(audio_tensor)
            
        return {
            "status": "success",
            "video_fake_score": vision_score,
            "audio_fake_score": audio_score,
            "extracted_ocr_text": extracted_text
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temporary files (Optional, but good practice)
        pass
