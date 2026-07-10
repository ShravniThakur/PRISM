from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from layer2.module1.scripts.inference_pipeline import TextThreatAnalyzer

router = APIRouter(prefix="/analyze", tags=["Text Threat Detection (Module 1)"])

# Initialize analyzer globally
analyzer = TextThreatAnalyzer()

class TextAnalysisRequest(BaseModel):
    text: str
    source_type: str = "email"

@router.post("/text")
async def analyze_text_endpoint(request: TextAnalysisRequest):
    """
    Analyzes text using the FinBERT sequence classifier and the URL Typo-Squat Analyzer.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
    try:
        result = await analyzer.analyze_message(text=request.text, source_type=request.source_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
