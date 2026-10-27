import urllib.parse
import smtplib
import json
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional
from config import DATA_DIR

SETTINGS_PATH = DATA_DIR / "email_settings.json"

def get_email_settings() -> Dict[str, str]:
    """Loads stored SMTP email settings if available."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "haripanand04@gmail.com",
        "sender_password": ""
    }

def save_email_settings(settings: Dict[str, Any]):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def generate_cold_email(profile: Dict[str, Any], job: Dict[str, Any], base_url: str = "") -> Dict[str, str]:
    """
    Generates a personalized cold email for HR/Hiring Managers
    at Indian robotics & embedded hardware companies, including direct resume links.
    """
    candidate_name = profile.get("name", "Hariprasad Anand")
    candidate_email = profile.get("email", "haripanand04@gmail.com")
    candidate_phone = profile.get("phone", "+91 9995075462")
    candidate_location = profile.get("location", "Alappuzha, Kerala")
    candidate_linkedin = profile.get("linkedin", "https://www.linkedin.com/in/hari-prasad-anand-90638126a/")
    candidate_github = profile.get("github", "https://github.com/Hhaarii")

    company_name = job.get("company", "the team")
    job_title = job.get("title", "Robotics & Embedded Engineer")
    recipient_email = job.get("contact_email", "")
    job_id = job.get("job_id", "")

    # Subject line formatted for high open rates
    subject = f"Application: {job_title} - {candidate_name} ({candidate_location})"

    resume_link_section = ""
    if base_url and job_id:
        resume_link_section = f"\n- Tailored Resume (PDF): {base_url}/api/resume/{job_id}\n"

    body = f"""Dear Hiring Team at {company_name},

I hope this email finds you well.

I am writing to express my strong interest in engineering opportunities in {job_title} at {company_name}. I hold a B.Tech in Robotics and Automation from Toc H Institute of Science and Technology and currently work as a Robotics Engineer (R&D) at SMEC Automation.

My hands-on technical foundation aligns directly with {company_name}'s work:
1. Embedded Firmware & Hardware Bring-Up: Designed and brought up custom ARM-based PCBs using KiCad; extensive debugging with ST-Link (SWD), logic analyzers, and protocols (SPI, I2C, UART, Modbus).
2. Autonomous Robotics & Vision: Developed autonomous ground vehicles utilizing ROS 2, Nav2, SLAM, and computer vision pipelines (OpenCV, YOLO, InsightFace).
3. RF & IoT Telemetry: Built and calibrated 915 MHz RF communication links (RFM69HCW) with zero-packet loss and orchestrated MQTT multi-device systems over Tailscale.
4. Key Projects: Engineered an Autonomous Mapping UGV (ROS 2/STM32), a vision-based Agricultural Rover with a 4-DOF manipulator, and an AI Chatbot system for SMEC Automation.

I am based in Kerala and open to on-site roles in Kochi, Bangalore, or remote/hybrid positions. 

I would welcome the opportunity to connect for a brief discussion. Please find my credentials and links below:
- GitHub: {candidate_github}
- LinkedIn: {candidate_linkedin}{resume_link_section}- Phone: {candidate_phone}

I have attached my tailored resume for your review. Thank you for your time and consideration.

Warm regards,

{candidate_name}
{candidate_email} | {candidate_phone}
Alappuzha, Kerala, India
"""

    # Generate mailto link
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    mailto_url = f"mailto:{recipient_email}?subject={encoded_subject}&body={encoded_body}"

    return {
        "to": recipient_email,
        "subject": subject,
        "body": body,
        "mailto_url": mailto_url
    }

def send_email_with_pdf_attachment(
    recipient_email: str,
    subject: str,
    body: str,
    pdf_path: Path,
    settings: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Sends email directly via SMTP with the tailored PDF resume attached.
    Works seamlessly with Gmail (using App Password) or any corporate SMTP server.
    """
    if not settings:
        settings = get_email_settings()

    sender_email = settings.get("sender_email")
    sender_password = settings.get("sender_password")
    smtp_server = settings.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(settings.get("smtp_port", 587))

    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "Email password not configured. Please enter your Gmail App Password in Email Settings."
        }

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach body
        msg.attach(MIMEText(body, 'plain'))

        # Attach PDF
        if pdf_path and Path(pdf_path).exists():
            with open(pdf_path, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header('Content-Disposition', 'attachment', filename=Path(pdf_path).name)
                msg.attach(pdf_attachment)
        else:
            return {"success": False, "error": f"PDF file not found at {pdf_path}"}

        # Send via TLS
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        return {"success": True, "message": f"Email with attached PDF successfully delivered to {recipient_email}!"}
    except Exception as e:
        return {"success": False, "error": str(e)}
