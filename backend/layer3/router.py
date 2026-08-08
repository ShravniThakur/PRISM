from __future__ import annotations
import os
import asyncio
import httpx
import tempfile
import shutil
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from layer3.central_brain import CentralBrain
from layer3.scripts.metadata_extractor import get_domain_age_days
from layer3.scripts.llm_reporter import generate_threat_report
from layer3.db import get_db, ScanHistory, User
from layer3.auth_router import get_current_user, get_current_user_optional
from layer3.scripts.email_reporter import send_threat_report_email

log = logging.getLogger(__name__)

router = APIRouter(prefix="/brain", tags=["Central Brain Scoring Engine"])


def _validate_service_url(name: str, url: str, fallback: str) -> str:
    """Validate a microservice URL and warn loudly if it contains unresolved
    shell variables (e.g. '$PORT') — a common Render env-var misconfiguration."""
    if "$" in url:
        log.error(
            "[CONFIG] %s=%r contains an unresolved shell variable. "
            "Render does not expand $VAR references inside env-var values. "
            "Set the full URL (e.g. https://your-service.onrender.com) in the "
            "Render dashboard, or delete the env var to use the auto-computed default. "
            "Falling back to %s.",
            name, url, fallback
        )
        return fallback
    return url


LAYER1_URL = _validate_service_url(
    "LAYER1_URL",
    os.getenv("LAYER1_URL", "http://localhost:8000"),
    "http://localhost:8000",
)
LAYER2_URL = _validate_service_url(
    "LAYER2_URL",
    os.getenv("LAYER2_URL", "http://localhost:8001"),
    "http://localhost:8001",
)

# Initialize Central Brain globally
brain = CentralBrain()

class ScoreRequest(BaseModel):
    text_score: float
    video_score: float
    audio_score: float
    domain: Optional[str] = None
    is_authenticated_sender: int
    raw_text: Optional[str] = None

@router.post("/orchestrate")
async def orchestrate_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    domain: Optional[str] = Form(None),
    entity_id: Optional[str] = Form(None),
    signature: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional)
):
    if not file and not text:
        raise HTTPException(status_code=400, detail="Must provide file or text")

    temp_file_path = None
    open_files = []
    
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            tasks = []
            
            # 1. Layer 1 Auth
            auth_data = {}
            if text:
                auth_data["text"] = text
            if entity_id:
                auth_data["entity_id"] = entity_id
            if signature:
                auth_data["signature_b64"] = signature
    
            auth_files = None
            if file:
                # Spool to disk to avoid Out-Of-Memory errors with large videos
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    temp_file_path = tmp.name
                    
                f1 = open(temp_file_path, "rb")
                open_files.append(f1)
                auth_files = {"file": (file.filename, f1, file.content_type)}
    
            tasks.append(client.post(f"{LAYER1_URL}/verify", data=auth_data, files=auth_files))
    
            # 2. Layer 2 Media
            if file:
                f2 = open(temp_file_path, "rb")
                open_files.append(f2)
                media_files = {"file": (file.filename, f2, file.content_type)}
                tasks.append(client.post(f"{LAYER2_URL}/analyze/media", files=media_files))
            else:
                async def dummy_media():
                    class Dummy:
                        status_code = 200
                        def json(self): return {}
                    return Dummy()
                tasks.append(dummy_media())
                
            # Wait for Auth and Media to finish
            results = await asyncio.gather(*tasks, return_exceptions=True)
            auth_res, media_res = results

            # Helper to safely get json from a result
            def safe_json(res, default={}):
                if isinstance(res, Exception):
                    print(f"Microservice exception: {res}")
                    return default
                if getattr(res, "status_code", 500) != 200:
                    print(f"Microservice error: {getattr(res, 'text', 'Unknown')}")
                    return default
                try:
                    return res.json()
                except Exception:
                    return default

            auth_data = safe_json(auth_res)
            media_data = safe_json(media_res)
            
            # 3. Combine initial text with OCR text, then run Layer 2 Text
            combined_text = text or ""
            is_ocr_only = not combined_text.strip()
            
            if media_data.get('extracted_ocr_text'):
                combined_text += "\n" + media_data['extracted_ocr_text']
                
            text_data = {}
            if combined_text.strip():
                try:
                    src_type = "ocr" if is_ocr_only else "user_input"
                    text_res = await client.post(f"{LAYER2_URL}/analyze/text", json={"text": combined_text.strip(), "source_type": src_type})
                    text_data = safe_json(text_res)
                except Exception as e:
                    print(f"Error calling text analysis: {e}")

        txt_score = text_data.get('final_text_score', 0.0)
        vid_score = media_data.get('video_fake_score', 0.0)
        aud_score = media_data.get('audio_fake_score', 0.0)
        
        is_auth = auth_data.get('is_authenticated_sender', 0)
            
        # Extract domain from text if not provided
        if not domain and combined_text:
            import re
            from urllib.parse import urlparse
            urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', combined_text)
            if urls:
                first_url = urls[0]
                if not first_url.startswith('http'):
                    first_url = 'http://' + first_url
                domain = urlparse(first_url).netloc

        # Call Central Brain
        domain_age = get_domain_age_days(domain)
        result = brain.calculate_final_threat(
            text_score=txt_score,
            video_score=vid_score,
            audio_score=aud_score,
            domain_age_days=domain_age,
            is_authenticated_sender=is_auth
        )
        
        has_media = file is not None
        llm_report = generate_threat_report(
            text_score=txt_score,
            video_score=vid_score,
            audio_score=aud_score,
            domain_age=domain_age,
            is_authenticated=is_auth,
            final_score=result["threat_probability"],
            raw_text=combined_text,
            has_media=has_media
        )
        
        scan_record = ScanHistory(
            user_id=user.id if user else None,
            text_score=txt_score,
            video_score=vid_score,
            audio_score=aud_score,
            is_authenticated_sender=is_auth,
            domain=domain,
            raw_context_text=combined_text,
            final_score=result["threat_probability"],
            classification=result["classification"],
            llm_threat_report=llm_report
        )
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)
        
        result["scan_id"] = scan_record.id
        result["llm_threat_report"] = llm_report
        # When the sender is cryptographically authenticated, zero out all
        # sub-scores in the response so the dashboard shows 0% everywhere
        # and no forensic red flags are raised. Raw scores are still stored
        # in the DB for audit purposes.
        if is_auth == 1:
            result["features_used"] = {
                "video_score": 0.0,
                "audio_score": 0.0,
                "text_score": 0.0,
                "is_auth": True
            }
        else:
            result["features_used"] = {
                "video_score": vid_score,
                "audio_score": aud_score,
                "text_score": txt_score,
                "is_auth": False
            }
        
        if user and user.email:
            background_tasks.add_task(send_threat_report_email, user.email, llm_report, result["threat_probability"], str(scan_record.id), result["features_used"])
            
        return result

    except BaseException as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for f in open_files:
            f.close()
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.post("/score")
def score_endpoint(request: ScoreRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: Optional[User] = Depends(get_current_user_optional)):
    """
    Accepts raw features from all PRISM microservices, dynamically looks up
    the domain age via WHOIS, and predicts the final threat classification.
    """
    try:
        # 1. Dynamically extract domain age via WHOIS
        domain_age = get_domain_age_days(request.domain)
        
        # 2. Score via Random Forest
        result = brain.calculate_final_threat(
            text_score=request.text_score,
            video_score=request.video_score,
            audio_score=request.audio_score,
            domain_age_days=domain_age,
            is_authenticated_sender=request.is_authenticated_sender
        )
        
        # 3. Generate LLM Threat Report
        llm_report = generate_threat_report(
            text_score=result["features_used"]["text_score"],
            video_score=result["features_used"]["video_score"],
            audio_score=result["features_used"]["audio_score"],
            domain_age=domain_age,
            is_authenticated=request.is_authenticated_sender,
            final_score=result["threat_probability"],
            raw_text=request.raw_text
        )
        
        # 4. Save to Database
        scan_record = ScanHistory(
            user_id=user.id if user else None,
            text_score=result["features_used"]["text_score"],
            video_score=result["features_used"]["video_score"],
            audio_score=result["features_used"]["audio_score"],
            is_authenticated_sender=request.is_authenticated_sender,
            domain=request.domain,
            raw_context_text=request.raw_text,
            final_score=result["threat_probability"],
            classification=result["classification"],
            llm_threat_report=llm_report
        )
        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)
        
        result["scan_id"] = scan_record.id
        result["llm_threat_report"] = llm_report
        if request.is_authenticated_sender == 1:
            result["features_used"] = {
                "video_score": 0.0,
                "audio_score": 0.0,
                "text_score": 0.0,
                "is_auth": True
            }
        else:
            result["features_used"] = {
                "video_score": result["features_used"]["video_score"],
                "audio_score": result["features_used"]["audio_score"],
                "text_score": result["features_used"]["text_score"],
                "is_auth": False
            }
        
        if user and user.email:
            background_tasks.add_task(send_threat_report_email, user.email, llm_report, result["threat_probability"], str(scan_record.id), result["features_used"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history(db: Session = Depends(get_db), limit: int = 50, user: User = Depends(get_current_user)):
    """Fetch recent scans for the history tab."""
    scans = db.query(ScanHistory).filter(ScanHistory.user_id == user.id).order_by(ScanHistory.timestamp.desc()).limit(limit).all()
    return scans

@router.get("/report/{scan_id}")
def get_report(scan_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Fetch a detailed threat report by scan ID."""
    scan = db.query(ScanHistory).filter(ScanHistory.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this scan")
    return scan
