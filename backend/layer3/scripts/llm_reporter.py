from __future__ import annotations
import os
from groq import Groq
from dotenv import load_dotenv

# Load .env file from backend directory (two levels up from scripts/)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path)

def generate_threat_report(text_score: float, video_score: float, audio_score: float, domain_age: int, is_authenticated: int, final_score: float, raw_text: str = None, has_media: bool = False) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "LLM Threat Report unavailable: GROQ_API_KEY not configured."
        
    client = Groq(api_key=api_key)
    
    # Smart Prompt Engineering for OCR/Text
    text_analysis_instructions = ""
    if raw_text:
        if is_authenticated:
            text_analysis_instructions = f"\n\nWe extracted the following text from the asset:\n'{raw_text}'\nNOTE: This asset is cryptographically verified to be from an official entity. Do not mention any AI models or threat scores; simply reassure the investor that this text is a genuine, safe advisory."
        elif text_score > 0.70:
            text_analysis_instructions = f"\n\nWe extracted the following text from the asset. The AI linguistic model flagged it as highly suspicious (Score: {text_score:.2f}). Please explicitly mention this text in your analysis and explain why it is manipulative or dangerous:\n'{raw_text}'"
        else:
            text_analysis_instructions = f"\n\nWe extracted the following text from the asset. However, the AI linguistic model deemed it benign (Score: {text_score:.2f}). Do NOT treat this text as malicious. It is likely just harmless background OCR text. You can ignore it or mention it is harmless:\n'{raw_text}'"

    media_signals = ""
    if has_media:
        media_signals = f"\n    - Video Deepfake Probability: {video_score:.2f} (0.00 = Authentic, 1.00 = Fake)\n    - Audio Deepfake Probability: {audio_score:.2f} (0.00 = Authentic, 1.00 = Fake)"

    prompt = f"""You are PRISM, an elite cybersecurity AI. Analyze the following threat signals and generate a structured JSON threat report for a retail investor. 
    
    Threat Signals:
    - Overall Threat Score: {final_score:.2f} (0=Safe, 100=Malicious){media_signals}
    - Domain Age: {f"{domain_age} days" if domain_age != 99999 else "N/A (No Domain Provided)"}
    - Cryptographically Authenticated: {"Yes" if is_authenticated else "No"}
    {text_analysis_instructions}
    
    Instructions:
    1. You must respond ONLY with a valid JSON object. Do not include markdown formatting or extra text.
    2. Maintain a cold, authoritative, cybersecurity tone in your writing.
    3. CRITICAL: If the asset is Cryptographically Authenticated (Yes), explicitly state that it is a genuine official communication. Do not mention AI threat scores or false positives; focus entirely on the fact that the cryptographic signature proves its safety.
    4. CRITICAL: If the asset is NOT authenticated and a specific sub-score is high but the Overall Threat Score is low, explicitly explain this discrepancy in the first paragraph.
    
    JSON Schema:
    {{
      "summary": [
        "Paragraph 1 summarizing the most critical factors that led to this score.",
        "Paragraph 2 giving the final verdict and explanation."
      ],
      "recommended_actions": [
        {{
          "title": "IMMEDIATE ACTION",
          "description": "Actionable advice on what the investor should do right now."
        }},
        {{
          "title": "PRECAUTION",
          "description": "Secondary advice or warnings."
        }}
      ]
    }}
    
    Note: Generate EXACTLY 4 recommended_actions with appropriate titles (e.g., IMMEDIATE ACTION, PRECAUTION, VERIFICATION, SECURITY TIP).
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a cyber security analysis system that outputs strictly in valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        return f'{{"summary": ["LLM Report Generation Failed: {str(e)}"], "recommended_actions": []}}'
