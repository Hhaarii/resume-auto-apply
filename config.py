import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESUMES_DIR = DATA_DIR / "resumes"
TAILORED_DIR = DATA_DIR / "tailored_resumes"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "applications.db"
MASTER_PROFILE_PATH = DATA_DIR / "master_profile.json"

# Ensure all critical directories exist
RESUMES_DIR.mkdir(parents=True, exist_ok=True)
TAILORED_DIR.mkdir(parents=True, exist_ok=True)

# Default Job Search & Filtering Preferences tailored for Hariprasad Anand
SEARCH_CONFIG = {
    # Target roles tailored to Robotics, Embedded Systems, Firmware, and Computer Vision
    "target_roles": [
        "Robotics Engineer",
        "Embedded Systems Engineer",
        "Firmware Engineer",
        "Robotics Software Engineer",
        "Computer Vision Engineer",
        "IoT Engineer",
        "Automation Engineer",
        "Hardware Engineer",
        "ROS Developer"
    ],
    "target_locations": ["Remote", "India", "Bangalore", "Hyderabad", "Kochi", "Any"],
    "remote_only": False,
    # Minimum ATS / skill match score (0-100) to qualify for auto-tailoring and applying
    "min_match_score": 60,
    # Excluded keywords
    "exclude_keywords": ["Senior Director", "Vice President", "Staff", "Principal", "Internship", "Unpaid"],
    # Maximum applications to process per batch
    "max_applications_per_run": 5
}

# Supported Free Public Job APIs
JOB_APIS = {
    "remoteok": "https://remoteok.com/api",
    "jobicy": "https://jobicy.com/api/v2/remote-jobs",
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
}

# LLM & AI Tailoring Configuration
LLM_CONFIG = {
    "provider": os.getenv("LLM_PROVIDER", "gemini"), # "gemini", "openai", or "heuristic"
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "model_name": os.getenv("LLM_MODEL", "gemini-1.5-flash"),
    "temperature": 0.3
}

# Browser / Auto-Applier Configuration
BROWSER_CONFIG = {
    "headless": False,  # Headful so user can see what the co-pilot is filling
    "slow_mo_ms": 600,   # Human-like delay between form actions
    "timeout_ms": 30000,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
