from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from layer3.central_brain import CentralBrain
from layer3.scripts.metadata_extractor import get_domain_age_days
from layer3.scripts.llm_reporter import generate_threat_report
from layer3.db import get_db, ScanHistory

router = APIRouter(prefix="/brain", tags=["Central Brain Scoring Engine"])

# Initialize Central Brain globally
brain = CentralBrain()

class ScoreRequest(BaseModel):
    text_score: float
    video_score: float
    audio_score: float
    domain: Optional[str] = None
    is_authenticated_sender: int
    raw_text: Optional[str] = None
    segmented_text_scores: list[float] = []
    segmented_video_scores: list[float] = []
    segmented_audio_scores: list[float] = []

@router.post("/score")
def score_endpoint(request: ScoreRequest, db: Session = Depends(get_db)):
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
            text_score=request.text_score,
            video_score=request.video_score,
            audio_score=request.audio_score,
            domain_age=domain_age,
            is_authenticated=request.is_authenticated_sender,
            final_score=result["threat_probability"],
            raw_text=request.raw_text
        )
        
        # 4. Save to Database
        scan_record = ScanHistory(
            text_score=request.text_score,
            video_score=request.video_score,
            audio_score=request.audio_score,
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
        result["timeline_data"] = {
            "video": request.segmented_video_scores,
            "audio": request.segmented_audio_scores,
            "text": request.segmented_text_scores
        }
        result["features_used"] = {
            "video_score": request.video_score,
            "audio_score": request.audio_score,
            "text_score": request.text_score
        }
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history(db: Session = Depends(get_db), limit: int = 50):
    """Fetch recent scans for the history tab."""
    scans = db.query(ScanHistory).order_by(ScanHistory.timestamp.desc()).limit(limit).all()
    return scans

@router.get("/report/{scan_id}")
def get_report(scan_id: str, db: Session = Depends(get_db)):
    """Fetch a detailed threat report by scan ID."""
    scan = db.query(ScanHistory).filter(ScanHistory.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
