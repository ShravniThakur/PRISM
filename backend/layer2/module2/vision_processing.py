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
                # 1. Image Preprocessing for OCR
                # Convert full frame to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Apply Gaussian Blur to remove compression artifacts
                blur = cv2.GaussianBlur(gray, (5,5), 0)
                
                # Apply Otsu's thresholding to binarize the image (black text on white background or vice versa)
                _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Convert thresholded image to PIL for Tesseract
                pil_img = Image.fromarray(thresh)
                
                # Use PSM 11 (Sparse text) to find as much text as possible in no particular order
                custom_config = r'--psm 11'
                text = pytesseract.image_to_string(pil_img, config=custom_config).strip()
                
                if text:
                    # Clean up random Tesseract noise (keep alphanumeric and basic punctuation)
                    cleaned = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', text)
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    if len(cleaned) > 2: # Ignore 1-2 character random noise
                        ocr_texts.append(cleaned)
                    
            frame_count += 1
            
        cap.release()
        
        # Deduplicate and join OCR text while preserving chronological order
        unique_text = list(dict.fromkeys(ocr_texts))
        full_ocr_text = " ".join(unique_text)
        
        return {
            "ocr_text": full_ocr_text
        }
