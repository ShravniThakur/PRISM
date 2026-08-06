import os
import gradio as gr
import uvicorn
from layer2.main import app as fastapi_app

# Ensure HuggingFace models are cached to a persistent directory
os.environ.setdefault("HF_HOME", "/home/user/.cache/huggingface")

# Create a minimal Gradio UI to satisfy Hugging Face's requirements
demo = gr.Interface(
    fn=lambda text: "PRISM Layer 2 AI Engine is running! Use /docs for the FastAPI interface.",
    inputs=gr.Textbox(label="Ping", placeholder="Type anything..."),
    outputs=gr.Textbox(label="Status"),
    title="PRISM AI Engine API",
    description="This is the AI microservice for PRISM. Use `/docs` for the full FastAPI Swagger UI and `/analyze/text` or `/analyze/media` endpoints."
)

# Mount Gradio at /ui on the FastAPI app so both are served together
app = gr.mount_gradio_app(fastapi_app, demo, path="/ui")

if __name__ == "__main__":
    # HuggingFace Spaces requires the server to bind on 0.0.0.0:7860
    uvicorn.run(app, host="0.0.0.0", port=7860)
