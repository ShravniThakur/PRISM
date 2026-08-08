import os

# ── CRITICAL: resolve Render's dynamic PORT before any layer is imported ──────
# Layer 1 and Layer 3 are co-located in this single Render process.
# Render assigns a dynamic PORT (e.g. 10000), NOT always 8000.
# Layer 3 calls Layer 1 over HTTP using LAYER1_URL; if that env var is not set
# it defaults to http://localhost:8000 which nothing listens on → silent
# connection-refused → is_authenticated_sender=0 → every asset shows
# "Unauthenticated" even when legitimately signed.
#
# setdefault only writes if the key isn't already in the environment, so an
# explicit LAYER1_URL in the Render dashboard still takes precedence.
_port = os.environ.get("PORT", "8000")
# Layer 1 is mounted at /layer1 in this unified render_app, so the
# internal base URL must include that prefix.
os.environ.setdefault("LAYER1_URL", f"http://localhost:{_port}/layer1")

# ── Now safe to import layers (they read LAYER1_URL at module load time) ──────
from fastapi import FastAPI
from layer1.app.main import app as layer1_app
from layer3.main import app as layer3_app

# Unified entry point for Render Deployment
# This saves resources by hosting both Layer 1 and Layer 3 in a single web service.
render_app = FastAPI(
    title="PRISM Render Backend (Layer 1 & 3)",
    description="Unified API gateway hosting Authentication (Layer 1) and Orchestration (Layer 3)."
)

# CORS is handled by the individual microservices (Layer 1 and Layer 3).
# Do not add CORSMiddleware here to avoid duplicate Access-Control-Allow-Origin headers.

# Mount the individual microservices
render_app.mount("/layer1", layer1_app)
render_app.mount("/layer3", layer3_app)

@render_app.get("/")
def root():
    return {
        "message": "PRISM Backend is running.",
        "layer1_docs": "/layer1/docs",
        "layer3_docs": "/layer3/docs"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("render_app:render_app", host="0.0.0.0", port=port, reload=False)
