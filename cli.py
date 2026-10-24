import argparse
import sys
import os

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import json
from pathlib import Path
from config import SEARCH_CONFIG, TAILORED_DIR
from modules.database import init_db, save_or_update_job, get_jobs_by_status, update_job_status
from modules.resume_parser import load_or_create_master_profile
from modules.job_fetcher import fetch_all_jobs
from modules.matcher import analyze_job_match
from modules.tailor import tailor_resume, generate_cover_letter
from modules.pdf_generator import generate_pdf
from modules.applier import auto_fill_job_application
from modules.india_jobs import load_and_score_india_jobs
from modules.email_dispatcher import generate_cold_email

def scan_jobs():
    """Scans live job feeds, analyzes match scores against master profile, and saves to DB."""
    init_db()
    profile = load_or_create_master_profile()
    candidate_name = profile.get("name", "Candidate")
    print(f"\n[SCAN STARTED] Finding vacancies matching {candidate_name}'s profile...")

    jobs = fetch_all_jobs()
    matched_count = 0

    print(f"\n{'MATCH %':<8} | {'COMPANY':<22} | {'JOB TITLE':<30} | {'SOURCE'}")
    print("-" * 75)

    for job in jobs:
        score, matched_skills, missing_skills = analyze_job_match(job, profile)
        job["match_score"] = score
        job["matched_skills"] = matched_skills
        job["missing_skills"] = missing_skills

        save_or_update_job(job)

        if score >= SEARCH_CONFIG.get("min_match_score", 60):
            matched_count += 1
            print(f"{score:>5}%   | {job.get('company')[:20]:<22} | {job.get('title')[:28]:<30} | {job.get('source')}")

    print("-" * 75)
    print(f"[+] Scan Complete: Found {matched_count} high-matching positions (Score >= {SEARCH_CONFIG.get('min_match_score', 60)}%).")
    print("[+] All opportunities recorded in SQLite database.\n")

def tailor_resumes(limit: int = 5):
    """Generates tailored ATS resumes and PDFs for top matched jobs."""
    init_db()
    profile = load_or_create_master_profile()
    min_score = SEARCH_CONFIG.get("min_match_score", 60)
    top_jobs = get_jobs_by_status("discovered", min_score=min_score, limit=limit)

    if not top_jobs:
        print(f"[-] No untailored jobs found with score >= {min_score}%. Run 'python cli.py scan' first.")
        return

    print(f"\n[TAILORING PIPELINE] Generating customized ATS resumes for top {len(top_jobs)} opportunities...\n")

    for job in top_jobs:
        company = job.get("company")
        title = job.get("title")
        score = job.get("match_score")
        matched_skills = json.loads(job.get("matched_skills") or "[]")

        print(f"[*] Tailoring for: {title} @ {company} (Match Score: {score}%)")
        print(f"    Target Keywords: {', '.join(matched_skills[:6])}")

        # 1. Tailor profile data
        tailored_data = tailor_resume(profile, job, matched_skills)

        # 2. Render & Compile to ATS PDF
        pdf_path = generate_pdf(tailored_data, company, title)

        # 3. Update DB
        update_job_status(job.get("job_id"), "tailored", str(pdf_path), "Resume tailored & compiled to PDF")

    print(f"\n[+] All {len(top_jobs)} resumes tailored and exported to: {TAILORED_DIR}")

def apply_to_job(job_id: str = None):
    """Launches the semi-automated Co-Pilot for a specific job or the highest match."""
    init_db()
    profile = load_or_create_master_profile()

    if job_id:
        conn = __import__("sqlite3").connect(from_config_db := __import__("config").DB_PATH)
        conn.row_factory = __import__("sqlite3").Row
        c = conn.cursor()
        c.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        job = dict(c.fetchone() or {})
        conn.close()
    else:
        # Get highest scored tailored job
        tailored_jobs = get_jobs_by_status("tailored", min_score=0, limit=1)
        if not tailored_jobs:
            # Fall back to discovered
            tailored_jobs = get_jobs_by_status("discovered", min_score=60, limit=1)
        job = tailored_jobs[0] if tailored_jobs else None

    if not job:
        print("[-] No eligible jobs to apply. Run 'python cli.py scan' and 'python cli.py tailor' first.")
        return

    pdf_path = Path(job.get("tailored_resume_path") or "")
    if not pdf_path.exists():
        # Generate on the fly
        matched_skills = json.loads(job.get("matched_skills") or "[]")
        tailored_data = tailor_resume(profile, job, matched_skills)
        pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))

    # Launch assistant
    auto_fill_job_application(job, profile, pdf_path)

def scan_india():
    """Loads and matches all verified Indian robotics & embedded companies."""
    init_db()
    load_and_score_india_jobs()

def list_company_emails():
    """Prints all companies with verified HR contact emails and generates cold-email drafts."""
    init_db()
    profile = load_or_create_master_profile()
    import sqlite3
    conn = sqlite3.connect(__import__("config").DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE contact_email IS NOT NULL AND contact_email != '' ORDER BY match_score DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    if not rows:
        print("[-] No companies with emails found yet. Run 'python cli.py india' first.")
        return

    print("\n" + "=" * 95)
    print("   VERIFIED INDIAN ROBOTICS & EMBEDDED COMPANIES - DIRECT HR CONTACTS")
    print("=" * 95)
    print(f"{'COMPANY':<26} | {'LOCATION':<22} | {'HR / CAREERS EMAIL':<30} | {'SCORE'}")
    print("-" * 95)
    for r in rows:
        print(f"{r.get('company')[:25]:<26} | {r.get('location')[:20]:<22} | {r.get('contact_email')[:28]:<30} | {r.get('match_score')}%")
    print("-" * 95)
    print("\n[+] To see a pre-formatted cold email for any company, check your web dashboard (http://localhost:8000)")
    print("    or click the direct 'Send Email' button to open your mail client instantly!\n")

def run_auto_pipeline():
    """Runs the end-to-end flow: Scan -> Filter -> Tailor -> Co-Pilot."""
    print("==================================================================")
    print("   AUTOMATED RESUME UPDATER & APPLICATION ASSISTANT SYSTEM")
    print("==================================================================")
    scan_jobs()
    tailor_resumes(limit=3)
    
    print("\n[?] Would you like to launch the Co-Pilot to pre-fill the top application now?")
    choice = input("Press [Y] to launch Co-Pilot browser or [N] to exit: ").strip().lower()
    if choice == "y":
        apply_to_job()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Resume Updater & Job Application Assistant")
    parser.add_argument("command", choices=["scan", "tailor", "apply", "auto", "profile", "india", "emails"], help="Command to execute")
    parser.add_argument("--job-id", type=str, default=None, help="Target specific job ID for tailoring or applying")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to process")

    args = parser.parse_args()

    if args.command == "scan":
        scan_jobs()
    elif args.command == "india":
        scan_india()
    elif args.command == "emails":
        list_company_emails()
    elif args.command == "tailor":
        tailor_resumes(limit=args.limit)
    elif args.command == "apply":
        apply_to_job(args.job_id)
    elif args.command == "auto":
        run_auto_pipeline()
    elif args.command == "profile":
        prof = load_or_create_master_profile()
        print(json.dumps(prof, indent=2))
