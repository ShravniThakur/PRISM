from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from layer2.module1.router import router as text_router
from layer2.module2.router import router as media_router

app = FastAPI(
    title="PRISM AI Threat Detection Engine",
    description="Layer 2: Artificial Intelligence models for analyzing Text, Videos, and Audio for phishing and deepfakes.",
    version="0.1.0",
)

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(text_router)
app.include_router(media_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "prism-ai-layer", "layer": 2}
