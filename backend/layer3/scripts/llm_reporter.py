import os
from groq import Groq
from dotenv import load_dotenv

# Load .env file from backend directory (two levels up from scripts/)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path)

def generate_threat_report(text_score: float, video_score: float, audio_score: float, domain_age: int, is_authenticated: int, final_score: float, raw_text: str = None) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "LLM Threat Report unavailable: GROQ_API_KEY not configured."
        
    client = Groq(api_key=api_key)
    
    # Smart Prompt Engineering for OCR/Text
    text_analysis_instructions = ""
    if raw_text:
        if text_score > 0.70:
            text_analysis_instructions = f"\n\nWe extracted the following text from the asset. The AI linguistic model flagged it as highly suspicious (Score: {text_score:.2f}). Please explicitly mention this text in your analysis and explain why it is manipulative or dangerous:\n'{raw_text}'"
        else:
            text_analysis_instructions = f"\n\nWe extracted the following text from the asset. However, the AI linguistic model deemed it benign (Score: {text_score:.2f}). Do NOT treat this text as malicious. It is likely just harmless background OCR text. You can ignore it or mention it is harmless:\n'{raw_text}'"

    prompt = f"""You are PRISM, an elite cybersecurity AI. Analyze the following threat signals and generate a concise, highly professional 2-paragraph threat report for a retail investor. 
    
    Threat Signals:
    - Overall Threat Score: {final_score:.2f} (0=Safe, 1=Malicious)
    - Video Deepfake Score: {video_score:.2f}
    - Audio Deepfake Score: {audio_score:.2f}
    - Domain Age: {domain_age} days
    - Cryptographically Authenticated: {"Yes" if is_authenticated else "No"}
    {text_analysis_instructions}
    
    Instructions:
    1. Do not greet the user. Start the report immediately.
    2. Write exactly two paragraphs. 
    3. Paragraph 1: Give the final verdict and summarize the most critical factors that led to this score (e.g., "This asset has been flagged as a critical threat due to...").
    4. Paragraph 2: Provide actionable advice on what the investor should do (e.g., "Do not click any links...").
    5. Maintain a cold, authoritative, cybersecurity tone.
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"LLM Threat Report generation failed: {str(e)}"
