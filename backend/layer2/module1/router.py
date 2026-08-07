from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from layer2.module1.scripts.inference_pipeline import TextThreatAnalyzer

router = APIRouter(prefix="/analyze", tags=["Text Threat Detection (Module 1)"])

# Initialize analyzer globally. Force CPU to avoid ZeroGPU CUDA exceptions
# since this runs on a background thread and is not decorated with @spaces.GPU.
analyzer = TextThreatAnalyzer(device="cpu")

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

@router.post("/test_raw")
async def test_raw(request: TextAnalysisRequest):
    return analyzer._classifier(request.text, truncation=True, max_length=256)
