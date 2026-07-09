import os
from media_ingest import MediaIngestor
from vision_processing import VisionProcessor
from audio_processing import AudioProcessor
from deepfake_scoring import DeepfakeScoringEngine

def run_test(video_path):
    print(f"\n--- Testing Pipeline on: {video_path} ---")
    if not os.path.exists(video_path):
        print(f"Error: File {video_path} not found.")
        return

    # Initialize components
    ingestor = MediaIngestor(upload_dir="layer2/module2/uploads")
    vision = VisionProcessor()
    audio = AudioProcessor()
    scorer = DeepfakeScoringEngine()

    print("1. Splitting Media...")
    paths = ingestor.process_upload(video_path)
    
    if paths.get("has_video"):
        print("2. Running Vision & OCR...")
        v_data = vision.extract_features(paths["video_only"])
        print(f"   - OCR Text: {v_data.get('ocr_text', '')}")
        print("3. Scoring Video...")
        v_score = scorer.score_video(paths["video_only"])
        print(f"   - Video Fake Score: {v_score:.4f}")
    
    if paths.get("has_audio"):
        print("4. Running Audio extraction...")
        a_tensor = audio.extract_features(paths["audio_only"])
        if a_tensor is not None:
            print("5. Scoring Audio...")
            a_score = scorer.score_audio(a_tensor)
            print(f"   - Audio Fake Score: {a_score:.6f}")

if __name__ == "__main__":
    # Test on the western benchmark videos
    run_test("sample_videos/western_real.mp4")
    run_test("sample_videos/western_fake.mp4")
    
