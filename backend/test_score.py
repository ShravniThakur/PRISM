import os
from layer2.module2.deepfake_scoring import DeepfakeScoringEngine

def test():
    try:
        print("Initializing engine...")
        engine = DeepfakeScoringEngine()
        print("Initialized.")
        
        video_path = "/Users/shravnithakur/Desktop/PRISM/backend/layer2/module2/sample_videos/western_real.mp4"
        print(f"Testing video: {video_path}")
        score = engine.score_video(video_path)
        print(f"Video score: {score}")
        
    except Exception as e:
        print("CRASH:", str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
