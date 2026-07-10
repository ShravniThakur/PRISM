from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from layer3.router import router as brain_router
from layer3.db import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PRISM Central Brain Engine",
    description="Layer 3: Random Forest Scoring Engine that aggregates signals and calculates the final Threat Score.",
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

app.include_router(brain_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "prism-central-brain", "layer": 3}
