import requests
import json
import glob

LAYER2_API = 'http://localhost:8001'
LAYER3_API = 'http://localhost:8002'

def test_video(filename):
    files = glob.glob(f'/Users/shravnithakur/Desktop/PRISM/**/{filename}', recursive=True)
    if not files:
        print(f"Could not find {filename}")
        return
    
    path = files[0]
    print(f"Uploading {path} to Layer 2 API...")
    
    with open(path, 'rb') as f:
        media_res = requests.post(f"{LAYER2_API}/analyze/media", files={"file": f}).json()
        
    print(f"Layer 2 Media Response: {json.dumps(media_res, indent=2)}")
    
    txt_score = 0
    seg_txt = []
    combined_text = ""
    
    if media_res.get('extracted_ocr_text'):
        is_pure_ocr = "[AUDIO TRANSCRIPT]:" not in media_res['extracted_ocr_text']
        source_type = "ocr" if is_pure_ocr else "video_transcript"
        
        text_res = requests.post(f"{LAYER2_API}/analyze/text", json={
            "text": media_res['extracted_ocr_text'],
            "source_type": source_type
        }).json()
        print(f"Layer 2 Text Response: {json.dumps(text_res, indent=2)}")
        txt_score = text_res.get('final_text_score', 0)
        seg_txt = text_res.get('segmented_text_scores', [])
        combined_text = media_res['extracted_ocr_text']
        
    print("\nGetting Final Score from Layer 3...")
    payload = {
        "text_score": txt_score,
        "video_score": media_res.get('video_fake_score', 0),
        "audio_score": media_res.get('audio_fake_score', 0),
        "domain": "",
        "is_authenticated_sender": 0,
        "raw_text": combined_text or "No text",
        "segmented_text_scores": seg_txt,
        "segmented_video_scores": media_res.get('segmented_video_scores', []),
        "segmented_audio_scores": media_res.get('segmented_audio_scores', [])
    }
    
    score_res = requests.post(f"{LAYER3_API}/brain/score", json=payload).json()
    print(f"\nFinal Layer 3 Response: {json.dumps(score_res, indent=2)}")
    
if __name__ == '__main__':
    test_video('western_fake.mp4')
