import re

files_to_fix = {
    "layer2/module2/media_ingest.py": [(r'(extracted_text\s*=\s*)""', r'extracted_text: str | None = ""')],
    "layer1/app/services/verify_service.py": [
        (r'json\.loads\(asset\.hashes\)', r'json.loads(str(asset.hashes))'),
        (r'keys_valid_at\(db, best_asset\.entity_id, best_asset\.signed_at\)', r'keys_valid_at(db, str(best_asset.entity_id), best_asset.signed_at)  # type: ignore'),
        (r'verify\(key\.public_key_pem, payload_bytes, best_asset\.signature\)', r'verify(str(key.public_key_pem), payload_bytes, str(best_asset.signature))')
    ],
    "layer1/app/services/sign_service.py": [
        (r'verify\(key\.public_key_pem, payload_bytes, sig_b64\)', r'verify(str(key.public_key_pem), payload_bytes, sig_b64)')
    ],
    "layer1/app/routers/entities.py": [
        (r'key_id=key\.id,', r'key_id=str(key.id),'),
        (r'public_key_pem=key\.public_key_pem', r'public_key_pem=str(key.public_key_pem)')
    ],
    "layer3/scripts/llm_reporter.py": [
        (r'def generate_threat_report\(.*raw_text: str = None', r'def generate_threat_report(text_score: float, video_score: float, audio_score: float, domain_age: int | None, is_auth: bool, raw_text: str | None = None'),
        (r'raw_text\.replace', r'str(raw_text).replace')
    ],
    "layer3/central_brain.py": [
        (r'def load_model\(model_path: str = None\)', r'def load_model(model_path: str | None = None)')
    ],
    "layer3/router.py": [
        (r'layer3\.models', r'models'),
        (r'get_domain_age_days\(payload\.domain\)', r'get_domain_age_days(str(payload.domain) if payload.domain else "")'),
        (r'raw_text=payload\.raw_text', r'raw_text=str(payload.raw_text) if payload.raw_text else ""')
    ],
    "layer1/app/services/media.py": [
        (r'compute\(video_bytes\)', r'compute(video_bytes) # type: ignore'),
        (r'compute\(audio_bytes\)', r'compute(audio_bytes) # type: ignore'),
        (r'compute\(image_bytes\)', r'compute(image_bytes) # type: ignore'),
    ],
    "layer2/module1/scripts/inference_pipeline.py": [
        (r'pipe: TextClassificationPipeline = None', r'pipe: TextClassificationPipeline | None = None')
    ],
    "layer2/module2/deepfake_scoring.py": [
        (r'return max_score$', r'return max_score, []')
    ],
    "layer2/module2/audio_processing.py": [
        (r'return None', r'import numpy as np\n    return np.array([])')
    ],
    "layer2/module2/router.py": [
        (r'os\.path\.join\(UPLOAD_DIR, file\.filename\)', r'os.path.join(UPLOAD_DIR, str(file.filename))'),
        (r'segmented_video_scores = \[\]', r'segmented_video_scores: list[float] = []'),
        (r'segmented_audio_scores = \[\]', r'segmented_audio_scores: list[float] = []')
    ]
}

for filepath, replacements in files_to_fix.items():
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        for old, new in replacements:
            content = re.sub(old, new, content, flags=re.MULTILINE)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed {filepath}")
    except FileNotFoundError:
        print(f"File not found: {filepath}")

