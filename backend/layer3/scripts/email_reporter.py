import os
import json
import resend
from dotenv import load_dotenv
import logging

log = logging.getLogger("email_reporter")

# Load .env file from backend directory (two levels up from scripts/)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path)

resend.api_key = os.getenv("RESEND_API_KEY")

# RESEND_FROM_EMAIL should be set to an address on a verified Resend domain.
# Default is Resend's sandbox address which only delivers to the account owner.
_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "PRISM Analysis <onboarding@resend.dev>")
if "onboarding@resend.dev" in _FROM_EMAIL:
    log.warning(
        "RESEND_FROM_EMAIL is using the Resend sandbox address (%s). "
        "Emails will only be delivered to your own Resend account email. "
        "Verify a domain at https://resend.com/domains and set "
        "RESEND_FROM_EMAIL=noreply@yourdomain.com to enable delivery to all users.",
        _FROM_EMAIL
    )

def send_threat_report_email(user_email: str, llm_report_str: str, final_score: float, scan_id: str, features_used: dict = None):
    if not resend.api_key:
        log.warning("RESEND_API_KEY not found. Skipping email report.")
        return

    try:
        report_data = json.loads(llm_report_str)
    except Exception as e:
        log.error(f"Failed to parse LLM report for email: {e}")
        report_data = {"summary": ["Could not parse threat report."], "recommended_actions": []}
        
    summary_sentences = report_data.get("summary", [])
    parsed_summary = []
    for s in summary_sentences:
        if isinstance(s, dict):
            parsed_summary.append(s.get("text", str(s)))
        else:
            parsed_summary.append(str(s))
            
    summary_html = "".join([f"<p>{s}</p>" for s in parsed_summary])
    
    actions_html = ""
    for action in report_data.get("recommended_actions", []):
        actions_html += f"""
        <div style="margin-bottom: 15px; padding: 15px; border-left: 4px solid #22d3ee; background-color: #f8f9fa;">
            <h4 style="margin: 0 0 5px 0; color: #1f2937;">{action.get('title', '')}</h4>
            <p style="margin: 0; color: #4b5563;">{action.get('description', '')}</p>
        </div>
        """

    score_color = "#39FF14" if final_score <= 25 else "#FFB800" if final_score <= 60 else "#FF3333"
    
    features = features_used or {}
    text_score_pct = round(features.get('text_score', 0.0) * 100, 1)
    video_score_pct = round(features.get('video_score', 0.0) * 100, 1)
    audio_score_pct = round(features.get('audio_score', 0.0) * 100, 1)
    
    subscores_html = f"""
    <div style="margin: 20px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px; text-align: center;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout: fixed;">
            <tr>
                <td width="33%" align="center" valign="top">
                    <p style="margin: 0; font-size: 12px; color: #6b7280; text-transform: uppercase;">Text Model</p>
                    <h2 style="margin: 5px 0 0 0; color: #374151;">{text_score_pct}%</h2>
                </td>
                <td width="33%" align="center" valign="top">
                    <p style="margin: 0; font-size: 12px; color: #6b7280; text-transform: uppercase;">Video Model</p>
                    <h2 style="margin: 5px 0 0 0; color: #374151;">{video_score_pct}%</h2>
                </td>
                <td width="33%" align="center" valign="top">
                    <p style="margin: 0; font-size: 12px; color: #6b7280; text-transform: uppercase;">Audio Model</p>
                    <h2 style="margin: 5px 0 0 0; color: #374151;">{audio_score_pct}%</h2>
                </td>
            </tr>
        </table>
    </div>
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #000; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="color: #22d3ee; margin: 0; letter-spacing: 2px;">PRISM</h1>
            <p style="color: #fff; margin: 5px 0 0 0; font-size: 12px; letter-spacing: 1px;">AI THREAT DETECTION ENGINE</p>
        </div>
        
        <div style="border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px; padding: 30px;">
            <h2 style="margin-top: 0;">Analysis Complete</h2>
            <p>Your recent threat analysis scan (ID: <code>{scan_id}</code>) has finished processing.</p>
            
            <div style="text-align: center; margin: 30px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
                <p style="margin: 0; font-size: 14px; font-weight: bold; color: #6b7280; text-transform: uppercase; letter-spacing: 1px;">Overall Threat Score</p>
                <h1 style="margin: 10px 0 0 0; font-size: 48px; color: {score_color};">{final_score}%</h1>
            </div>
            
            {subscores_html}

            <h3 style="border-bottom: 2px solid #f3f4f6; padding-bottom: 10px;">Analyst Summary</h3>
            {summary_html}

            <h3 style="border-bottom: 2px solid #f3f4f6; padding-bottom: 10px; margin-top: 30px;">Recommended Actions</h3>
            {actions_html}
            
            <p style="margin-top: 40px; font-size: 12px; color: #9ca3af; text-align: center;">
                This is an automated report from the PRISM Zero-Trust Analysis Engine.<br>
                Do not reply to this email.
            </p>
        </div>
    </body>
    </html>
    """

    try:
        resend.Emails.send({
            "from": _FROM_EMAIL,
            "to": [user_email],
            "subject": f"PRISM Threat Report - Score: {final_score}%",
            "html": html_content
        })
        log.info(f"Successfully sent threat report email to {user_email}")
    except Exception as e:
        log.error(f"Failed to send email via Resend: {e}")
