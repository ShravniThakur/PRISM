from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import entities, sign, verify

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PRISM Authentication Engine",
    description="Layer 1: cryptographic verification of official financial communications via signed fuzzy hashes (TLSH / pHash).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entities.router)
app.include_router(sign.router)
app.include_router(verify.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "prism-auth", "layer": 1}
