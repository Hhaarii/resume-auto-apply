# Automated Resume Updater & Application Co-Pilot

An intelligent, ATS-optimized pipeline that extracts your master resume, matches live engineering vacancies across public job boards (RemoteOK, Jobicy, Arbeitnow), tailors your resume for maximum ATS alignment, compiles professional PDFs, and assists you in pre-filling application forms via browser automation.

---

## 🚀 Key Features

1. **Master Profile Engine**:
   - Stores your verified achievements, skills, projects, and work history truthfully in `data/master_profile.json`.
   - Never hallucinates degrees or past employers.

2. **Smart Vacancy Aggregator & Matcher**:
   - Connects to public engineering job boards.
   - Computes weighted ATS match score (%) comparing JD keywords (ROS, STM32, ARM, OpenCV, Python, C++, etc.) with your profile.
   - Highlights matching keywords and identifies skill gaps.

3. **Dynamic Resume & Cover Letter Tailoring**:
   - Automatically adapts professional summary, re-orders skills to highlight JD requirements, and reorganizes project highlights.
   - Exports clean, ATS-compliant, single/multi-page PDFs using Playwright Chromium into `data/tailored_resumes/`.
   - Generates customized cover letters ready for submission.

4. **Semi-Automated Co-Pilot Application Submitter**:
   - Opens a headful browser session.
   - Auto-fills candidate fields (Name, Email, Phone, LinkedIn, GitHub, Portfolio).
   - Automatically attaches the generated tailored PDF resume.
   - Pre-fills the tailored cover letter into text areas.
   - Pauses for you to review and click **Submit**, ensuring 100% submission safety and zero bot bans.

5. **Visual Dashboard**:
   - Clean dark-mode web interface to monitor applications, view PDFs, and trigger scans.

---

## 📁 Directory Structure

```text
resume-auto-apply/
├── data/
│   ├── resumes/               # Place any original base PDF/DOCX resumes here
│   ├── tailored_resumes/      # Auto-generated ATS PDFs & HTML files
│   ├── master_profile.json    # Candidate profile (Hariprasad Anand)
│   └── applications.db        # SQLite database tracking jobs & application statuses
├── templates/
│   └── resume_template.html   # Clean ATS-compliant printable template
├── modules/
│   ├── database.py            # SQLite database manager
│   ├── resume_parser.py       # PDF/DOCX parser
│   ├── job_fetcher.py         # Multi-source live vacancy scraper & API client
│   ├── matcher.py             # ATS keyword matching & scoring engine
│   ├── tailor.py              # Resume & cover letter tailoring logic
│   ├── pdf_generator.py       # Playwright Chromium PDF compiler
│   └── applier.py             # Browser automation co-pilot
├── config.py                  # Search filters, role preferences, browser settings
├── cli.py                     # Command-line interface
└── dashboard.py               # Interactive web UI (FastAPI)
```

---

## 🛠️ Usage Commands

Run commands from `C:\Users\infok\.gemini\antigravity\scratch\resume-auto-apply`:

### 1. Scan Live Jobs
Scans job sources, scores relevance against your profile, and records them in the database:
```powershell
python cli.py scan
```

### 2. Tailor Resumes for Top Matches
Generates customized ATS resumes and compiles them to PDF for top positions:
```powershell
python cli.py tailor --limit 5
```

### 3. Launch Application Co-Pilot
Launches the browser assistant to auto-fill an application form and attach your tailored PDF:
```powershell
python cli.py apply
```
Or for a specific job:
```powershell
python cli.py apply --job-id <job_id>
```

### 4. Interactive Web Dashboard
Launches the visual dashboard:
```powershell
python dashboard.py
```
Open **`http://localhost:8000`** in your browser to view your matches, preview PDFs, and launch the co-pilot with one click.
