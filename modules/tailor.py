import copy
import re
from typing import Dict, Any

def tailor_resume(profile: Dict[str, Any], job: Dict[str, Any], matched_skills: list) -> Dict[str, Any]:
    """
    Creates a tailored copy of the candidate's master profile specifically aligned
    with the target job and company requirements for maximum ATS scoring.
    """
    tailored = copy.deepcopy(profile)
    job_title = job.get("title", "Robotics & Embedded Engineer")
    company = job.get("company", "the company")
    jd_text = f"{job_title} {job.get('description', '')}".lower()

    # 1. Tailor Professional Summary
    # Inject relevant keywords naturally into the summary
    key_focus = []
    if any(k in jd_text for k in ["ros", "ros2", "nav2", "slam", "robotics"]):
        key_focus.append("ROS/ROS 2 autonomous navigation")
    if any(k in jd_text for k in ["embedded", "stm32", "firmware", "microcontroller"]):
        key_focus.append("ARM-based embedded firmware & PCB hardware bring-up")
    if any(k in jd_text for k in ["opencv", "vision", "yolo", "computer vision"]):
        key_focus.append("real-time computer vision pipelines")
    if any(k in jd_text for k in ["rf", "wireless", "rfm69", "iot", "mqtt"]):
        key_focus.append("long-range RF & IoT telemetry")

    if not key_focus:
        key_focus = ["embedded systems", "robotics architecture", "autonomous platforms"]

    focus_str = ", ".join(key_focus)
    tailored["summary"] = (
        f"Dynamic and results-driven Robotics and Automation Engineer with demonstrated expertise in {focus_str}. "
        f"Experienced in the full product lifecycle from custom PCB design (KiCad) and ARM/STM32 board bring-up "
        f"to autonomous navigation (ROS 2/Nav2/SLAM) and computer vision. Eager to contribute technical rigor and "
        f"collaborative problem-solving to {company} as a {job_title}."
    )

    # 2. Re-order / Prioritize Skills for ATS
    for cat, items in tailored.get("skills", {}).items():
        # Move skills that match the JD to the front of each category
        matched_in_cat = [s for s in items if any(m.lower() in s.lower() or s.lower() in m.lower() for m in matched_skills)]
        remaining = [s for s in items if s not in matched_in_cat]
        tailored["skills"][cat] = matched_in_cat + remaining

    # 3. Re-order Projects based on relevance
    projects = tailored.get("projects", [])
    def project_relevance_score(proj):
        p_text = f"{proj.get('name', '')} {' '.join(proj.get('technologies', []))} {' '.join(proj.get('bullets', []))}".lower()
        score = 0
        for m in matched_skills:
            if m.lower() in p_text:
                score += 3
        return score

    tailored["projects"] = sorted(projects, key=project_relevance_score, reverse=True)

    return tailored

def generate_cover_letter(profile: Dict[str, Any], job: Dict[str, Any], matched_skills: list) -> str:
    """Generates a concise, high-impact cover letter tailored to the job vacancy."""
    name = profile.get("name", "Hariprasad Anand")
    company = job.get("company", "Hiring Team")
    title = job.get("title", "Position")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    top_skills = ", ".join(matched_skills[:4]) if matched_skills else "Robotics, Embedded Systems, and Firmware"

    letter = f"""Dear Hiring Team at {company},

I am writing to express my enthusiastic interest in the {title} position at {company}. With a degree in Robotics and Automation and direct industry experience at SMEC Automation, I have built a solid foundation across custom PCB design, ARM/STM32 firmware bring-up, and autonomous robotics platforms.

Given your focus on {top_skills}, my background directly aligns with your requirements:
- Embedded & Hardware: Designed and brought up custom ARM-based PCBs using KiCad and ST-Link (SWD), implementing critical protocols including SPI, UART, I2C, and Modbus.
- Autonomous Systems & Vision: Built autonomous mapping UGVs and rovers integrating ROS 2, Nav2, SLAM, and OpenCV/YOLO vision pipelines.
- Wireless & IoT: Engineered reliable 915 MHz RF communication links and secure MQTT multi-device orchestration architectures.

I am particularly excited about {company}'s work and would welcome the opportunity to discuss how my hands-on technical skills and problem-solving mindset can add immediate value to your engineering team.

Thank you for your time and consideration.

Warm regards,

{name}
{email} | {phone}
{profile.get('linkedin', '')}
"""
    return letter
