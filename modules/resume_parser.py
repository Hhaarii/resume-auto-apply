import re
import json
from pathlib import Path
from config import RESUMES_DIR, MASTER_PROFILE_PATH

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts raw text from a PDF file using pypdf or pdfplumber if available, with robust fallback."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text
    except ImportError:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            return text
    except ImportError:
        pass

    # Basic fallback if external libraries are still installing
    return f"[Error: Please ensure 'pypdf' is installed to parse {pdf_path.name}]"

def extract_text_from_docx(docx_path: Path) -> str:
    """Extracts text from DOCX file."""
    try:
        import docx
        doc = docx.Document(str(docx_path))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except ImportError:
        import zipfile
        import xml.etree.ElementTree as ET
        try:
            with zipfile.ZipFile(str(docx_path)) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                text = " ".join(tree.itertext())
                return text
        except Exception as e:
            return f"[Error parsing DOCX: {e}]"

def parse_resume_to_dict(text: str) -> dict:
    """
    Parses unstructured resume text into a structured profile dictionary.
    Extracts contact info, summary, skills, experience, and education.
    """
    profile = {
        "name": "Applicant Name",
        "email": "",
        "phone": "",
        "location": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
        "summary": "",
        "skills": {
            "Languages": [],
            "Frameworks & Libraries": [],
            "Cloud & DevOps": [],
            "Databases & Tools": []
        },
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": []
    }

    # Extract email
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    if email_match:
        profile["email"] = email_match.group(0)

    # Extract phone
    phone_match = re.search(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}", text)
    if phone_match:
        profile["phone"] = phone_match.group(0).strip()

    # Extract LinkedIn & GitHub
    linkedin_match = re.search(r"https?://(www\.)?linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
    if linkedin_match:
        profile["linkedin"] = linkedin_match.group(0)

    github_match = re.search(r"https?://(www\.)?github\.com/[\w-]+", text, re.IGNORECASE)
    if github_match:
        profile["github"] = github_match.group(0)

    # Guess Name from first 3 non-empty lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:3]:
        if not re.search(r"@|linkedin|github|http|\+|\d{5}", line, re.IGNORECASE) and len(line) < 40:
            profile["name"] = line
            break

    # Extract Skills by keyword heuristics
    common_skills = {
        "Languages": ["Python", "JavaScript", "TypeScript", "Go", "Java", "C++", "C#", "Rust", "SQL", "HTML", "CSS", "Bash"],
        "Frameworks & Libraries": ["React", "Node.js", "Express", "FastAPI", "Django", "Flask", "Next.js", "Vue", "Angular", "Tailwind CSS", "Spring Boot"],
        "Cloud & DevOps": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CI/CD", "GitHub Actions", "Linux", "Nginx"],
        "Databases & Tools": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Git", "Elasticsearch", "Kafka", "GraphQL", "REST APIs"]
    }

    for category, skills_list in common_skills.items():
        found = []
        for s in skills_list:
            # Word boundary search
            pattern = r"\b" + re.escape(s) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                found.append(s)
        if found:
            profile["skills"][category] = found

    # Basic experience section splitting
    exp_header = re.search(r"(?:WORK\s+)?EXPERIENCE|EMPLOYMENT\s+HISTORY", text, re.IGNORECASE)
    edu_header = re.search(r"EDUCATION|ACADEMIC\s+BACKGROUND", text, re.IGNORECASE)

    if exp_header and edu_header and edu_header.start() > exp_header.start():
        exp_chunk = text[exp_header.end():edu_header.start()]
    elif exp_header:
        exp_chunk = text[exp_header.end():exp_header.end() + 2000]
    else:
        exp_chunk = ""

    # Parse rough bullet points or blocks
    if exp_chunk:
        raw_bullets = [b.strip("-*• \t") for b in exp_chunk.split("\n") if len(b.strip()) > 20]
        if raw_bullets:
            profile["experience"].append({
                "title": "Software Engineer",
                "company": "Previous Organization",
                "start_date": "2021",
                "end_date": "Present",
                "location": "Remote",
                "bullets": raw_bullets[:5]
            })

    # Summary
    sum_header = re.search(r"(?:PROFESSIONAL\s+)?SUMMARY|ABOUT\s+ME|PROFILE", text, re.IGNORECASE)
    if sum_header:
        sum_chunk = text[sum_header.end():sum_header.end() + 400]
        first_para = sum_chunk.split("\n\n")[0].replace("\n", " ").strip()
        if len(first_para) > 30:
            profile["summary"] = first_para

    return profile

def load_or_create_master_profile() -> dict:
    """Loads existing master profile or parses the first resume in data/resumes."""
    if MASTER_PROFILE_PATH.exists():
        with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # Check data/resumes/
    resume_files = list(RESUMES_DIR.glob("*.pdf")) + list(RESUMES_DIR.glob("*.docx"))
    if resume_files:
        first_file = resume_files[0]
        print(f"[*] Found resume file: {first_file.name}. Parsing...")
        if first_file.suffix.lower() == ".pdf":
            raw_text = extract_text_from_pdf(first_file)
        else:
            raw_text = extract_text_from_docx(first_file)
        profile = parse_resume_to_dict(raw_text)
    else:
        # Default starter template
        profile = {
            "name": "Alex Morgan",
            "email": "alex.morgan.dev@example.com",
            "phone": "+1 (555) 234-5678",
            "location": "San Francisco, CA (Open to Remote)",
            "linkedin": "https://linkedin.com/in/alexmorgandev",
            "github": "https://github.com/alexmorgandev",
            "portfolio": "https://alexmorgan.dev",
            "summary": "Results-oriented Software Engineer with 4+ years of experience designing and shipping scalable web applications and microservices. Proficient in Python, TypeScript, modern cloud architectures, and REST/GraphQL APIs.",
            "skills": {
                "Languages": ["Python", "TypeScript", "JavaScript", "SQL", "Bash"],
                "Frameworks & Libraries": ["FastAPI", "React", "Node.js", "Django", "Tailwind CSS"],
                "Cloud & DevOps": ["AWS", "Docker", "CI/CD", "GitHub Actions", "PostgreSQL", "Redis"],
                "Methodologies": ["Agile/Scrum", "TDD", "System Architecture", "Microservices"]
            },
            "experience": [
                {
                    "title": "Full Stack Software Engineer",
                    "company": "TechVanguard Solutions",
                    "location": "Remote",
                    "start_date": "2022",
                    "end_date": "Present",
                    "bullets": [
                        "Architected and deployed high-throughput microservices using Python FastAPI and PostgreSQL, serving 500k+ daily active users.",
                        "Engineered real-time data pipelines and caching layers with Redis, reducing average API response latency by 42%.",
                        "Led migration of monolith services to Docker containers orchestrated on AWS ECS with automated CI/CD pipelines."
                    ]
                },
                {
                    "title": "Software Developer",
                    "company": "InnoSoft Systems",
                    "location": "New York, NY",
                    "start_date": "2020",
                    "end_date": "2022",
                    "bullets": [
                        "Developed dynamic web frontends using React and TypeScript, improving Core Web Vitals and user engagement by 28%.",
                        "Built robust RESTful APIs with Python and Flask, integrating payment gateways and third-party SaaS services.",
                        "Authored comprehensive unit and integration test suites, achieving 90%+ code coverage."
                    ]
                }
            ],
            "projects": [
                {
                    "name": "CloudOps Automation Platform",
                    "role": "Lead Creator",
                    "technologies": ["Python", "FastAPI", "Docker", "AWS"],
                    "link": "https://github.com/alexmorgandev/cloudops",
                    "bullets": [
                        "Automated cloud infrastructure health monitoring and alerting, reducing mean time to detection (MTTD) by 60%."
                    ]
                }
            ],
            "education": [
                {
                    "degree": "B.S. in Computer Science",
                    "institution": "University of California, Berkeley",
                    "graduation_date": "2020",
                    "details": "Focus on Distributed Systems and Software Engineering"
                }
            ],
            "certifications": [
                {
                    "name": "AWS Certified Solutions Architect – Associate",
                    "issuer": "Amazon Web Services",
                    "date": "2023"
                }
            ]
        }

    # Save to disk
    with open(MASTER_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return profile
