from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from layer3.central_brain import CentralBrain
from layer3.scripts.metadata_extractor import get_domain_age_days

router = APIRouter(prefix="/brain", tags=["Central Brain Scoring Engine"])

# Initialize Central Brain globally
brain = CentralBrain()

class ScoreRequest(BaseModel):
    text_score: float
    video_score: float
    audio_score: float
    domain: Optional[str] = None
    is_authenticated_sender: int

@router.post("/score")
async def score_endpoint(request: ScoreRequest):
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
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
