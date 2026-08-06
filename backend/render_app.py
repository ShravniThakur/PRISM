from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("render_app:render_app", host="0.0.0.0", port=port, reload=False)
