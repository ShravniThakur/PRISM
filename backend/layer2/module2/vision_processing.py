import cv2
import pytesseract
from PIL import Image
from facenet_pytorch import MTCNN
import torch
import numpy as np

class VisionProcessor:
    def __init__(self):
        # Initialize MTCNN for face cropping. Use MPS if available on Mac, else CPU.
        self.device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
        print(f"VisionProcessor initialized on device: {self.device}")
        
        # Initialize MTCNN for face extraction. Force CPU because of a known PyTorch MPS bug with Adaptive Pool
        self.mtcnn = MTCNN(keep_all=True, device='cpu')

    def extract_features(self, video_path: str, sample_rate_sec: float = 0.5) -> dict:
        """
        Extracts frames every `sample_rate_sec`. 
        Runs OCR on the frames, and crops faces.
        Returns the cropped face images (as numpy arrays) and concatenated OCR text.
        """
        if not video_path:
            return {"face_frames": [], "ocr_text": ""}
            
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if fps == 0:
            return {"face_frames": [], "ocr_text": ""}
            
        frame_interval = int(fps * sample_rate_sec)
        
        face_frames = []
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
                    ocr_texts.append(text)
                
                # 2. Face Cropping
                # MTCNN expects RGB PIL images or numpy arrays
                try:
                    face = self.mtcnn(pil_img)
                    if face is not None:
                        # MTCNN returns a 4D normalized tensor (Batch, C, H, W) because keep_all=True
                        for f in face:
                            face_frames.append(f)
                except Exception as e:
                    print(f"Face extraction error on frame {frame_count}: {e}")
                    
            frame_count += 1
            
        cap.release()
        
        # Deduplicate and join OCR text
        unique_text = list(set(ocr_texts))
        full_ocr_text = " ".join(unique_text)
        
        return {
            "face_frames": face_frames, # List of PyTorch tensors (faces)
            "ocr_text": full_ocr_text
        }
