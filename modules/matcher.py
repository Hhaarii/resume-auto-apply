import re
from typing import Dict, List, Tuple

# Comprehensive taxonomy of technical skills for Embedded, Robotics, Software, and AI
SKILL_TAXONOMY = {
    # Embedded & Hardware
    "stm32": "STM32",
    "esp32": "ESP32",
    "arm": "ARM Cortex",
    "arduino": "Arduino",
    "raspberry pi": "Raspberry Pi",
    "spi": "SPI",
    "i2c": "I2C",
    "uart": "UART",
    "usart": "USART",
    "modbus": "Modbus",
    "can": "CAN Bus",
    "canbus": "CAN Bus",
    "rf": "RF Communication",
    "rfm69": "RFM69",
    "kicad": "KiCad",
    "pcb": "PCB Design",
    "altium": "Altium",
    "rtos": "RTOS / FreeRTOS",
    "freertos": "FreeRTOS",
    "swd": "SWD / ST-Link",
    "plc": "PLC Programming",
    "firmware": "Firmware Engineering",
    "embedded c": "Embedded C",
    "microcontroller": "Microcontrollers",

    # Robotics & Automation
    "ros": "ROS",
    "ros 2": "ROS 2",
    "ros2": "ROS 2",
    "nav2": "Nav2",
    "slam": "SLAM",
    "gazebo": "Gazebo",
    "ugv": "UGV",
    "uav": "UAV / Drones",
    "mission planner": "Mission Planner",
    "lidar": "LiDAR",
    "kinematics": "Kinematics",
    "control systems": "Control Systems",
    "pid": "PID Control",

    # Computer Vision & AI
    "opencv": "OpenCV",
    "yolo": "YOLO",
    "computer vision": "Computer Vision",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "insightface": "InsightFace",
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "llm": "LLMs",
    "ollama": "Ollama",

    # Software & Protocols
    "python": "Python",
    "c++": "C++",
    "c": "C",
    "flask": "Flask",
    "django": "Django",
    "fastapi": "FastAPI",
    "mqtt": "MQTT",
    "git": "Git",
    "docker": "Docker",
    "linux": "Linux",
    "bash": "Bash",
    "solidworks": "SolidWorks",
    "cad": "CAD"
}

def extract_profile_skill_set(profile: dict) -> set:
    """Flattens all skills and keywords from user profile into a normalized set."""
    skills_set = set()
    
    # Direct skills categories
    for cat, items in profile.get("skills", {}).items():
        for s in items:
            skills_set.add(s.lower().strip())

    # Scan projects & experience for technologies
    for exp in profile.get("experience", []):
        text = f"{exp.get('title', '')} {' '.join(exp.get('bullets', []))}".lower()
        for key in SKILL_TAXONOMY:
            if re.search(r"\b" + re.escape(key) + r"\b", text):
                skills_set.add(key)

    for proj in profile.get("projects", []):
        for tech in proj.get("technologies", []):
            skills_set.add(tech.lower().strip())
        proj_text = " ".join(proj.get("bullets", [])).lower()
        for key in SKILL_TAXONOMY:
            if re.search(r"\b" + re.escape(key) + r"\b", proj_text):
                skills_set.add(key)

    return skills_set

def analyze_job_match(job: dict, profile: dict) -> Tuple[int, List[str], List[str]]:
    """
    Analyzes job description against candidate profile.
    Calculates weighted match score considering:
    - Core domain alignment (Robotics, Embedded, Hardware, Vision)
    - Keyword overlap density
    - Title relevance and role level
    """
    title = str(job.get("title", "")).lower()
    desc = str(job.get("description", "")).lower()
    job_text = f"{title} {desc}"
    profile_skills = extract_profile_skill_set(profile)

    # Disqualify clearly irrelevant non-engineering titles
    irrelevant_roles = ["pricing", "sales", "deal desk", "recruiter", "accountant", "hr", "legal", "payroll", "marketing", "content writer"]
    if any(irr in title for irr in irrelevant_roles):
        return 0, [], []

    jd_required_skills = set()
    for skill_key, formal_name in SKILL_TAXONOMY.items():
        pattern = r"\b" + re.escape(skill_key) + r"\b"
        if re.search(pattern, job_text):
            jd_required_skills.add(skill_key)

    if not jd_required_skills:
        return 20, [], []

    matched = []
    missing = []

    # High-value core skills for Hariprasad's domain
    core_skills = {"ros", "ros 2", "ros2", "stm32", "esp32", "arm", "kicad", "pcb", "firmware", "opencv", "yolo", "slam", "nav2", "modbus", "spi", "i2c", "uart", "rfm69"}

    core_match_count = 0
    for req in jd_required_skills:
        found = False
        for p_skill in profile_skills:
            if req in p_skill or p_skill in req:
                found = True
                break
        if found:
            matched.append(SKILL_TAXONOMY.get(req, req.capitalize()))
            if req in core_skills:
                core_match_count += 1
        else:
            missing.append(SKILL_TAXONOMY.get(req, req.capitalize()))

    # Calculate base score based on matched percentage and raw volume
    base_ratio = len(matched) / max(len(jd_required_skills), 1)
    
    # Volume score: having more overlapping skills yields higher confidence
    volume_factor = min(1.0, len(matched) / 5.0)  # max out at 5+ matching skills
    score = int((base_ratio * 0.5 + volume_factor * 0.5) * 80)

    # Title alignment bonus
    target_titles = ["robotics", "embedded", "firmware", "hardware", "ros", "vision", "automation", "software", "iot", "mechatronics"]
    if any(t in title for t in target_titles):
        score += 15

    # Core skill bonus
    if core_match_count > 0:
        score += min(20, core_match_count * 5)

    # Cap score between 0 and 99
    score = max(5, min(98, score))

    # Deduplicate lists
    matched = sorted(list(set(matched)))
    missing = sorted(list(set(missing)))

    return score, matched, missing
