import cv2
import pytesseract
from PIL import Image
import re
import numpy as np

class VisionProcessor:
    def __init__(self):
        print("VisionProcessor initialized (OCR Only)")

    def extract_features(self, video_path: str, sample_rate_sec: float = 0.5) -> dict:
        """
        Extracts frames every `sample_rate_sec` and runs OCR on them.
        Returns the concatenated OCR text.
        """
        if not video_path:
            return {"ocr_text": ""}
            
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if fps == 0:
            return {"ocr_text": ""}
            
        frame_interval = max(1, int(fps * sample_rate_sec))
        
        ocr_texts = []
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                # 1. OCR Processing
                # Convert frame to PIL Image for Tesseract
                pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                text = pytesseract.image_to_string(pil_img).strip()
                if text:
                    # Clean up random Tesseract noise (keep alphanumeric and basic punctuation)
                    cleaned = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', text)
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    if len(cleaned) > 1: # Ignore single random characters
                        ocr_texts.append(cleaned)
                    
            frame_count += 1
            
        cap.release()
        
        # Deduplicate and join OCR text while preserving chronological order
        unique_text = list(dict.fromkeys(ocr_texts))
        full_ocr_text = " ".join(unique_text)
        
        return {
            "ocr_text": full_ocr_text
        }
