import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import DB_PATH

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        location TEXT,
        url TEXT,
        contact_email TEXT,
        source TEXT,
        description TEXT,
        match_score INTEGER DEFAULT 0,
        matched_skills TEXT,
        missing_skills TEXT,
        status TEXT DEFAULT 'discovered',
        tailored_resume_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        applied_at TIMESTAMP,
        notes TEXT
    )
    """)
    try:
        cursor.execute("ALTER TABLE applications ADD COLUMN contact_email TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

def save_or_update_job(job: dict) -> bool:
    """Inserts a new job or updates match details if not applied yet."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO applications (
            job_id, company, title, location, url, contact_email, source, description,
            match_score, matched_skills, missing_skills, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?)
        ON CONFLICT(job_id) DO UPDATE SET
            contact_email = COALESCE(excluded.contact_email, applications.contact_email),
            match_score = excluded.match_score,
            matched_skills = excluded.matched_skills,
            missing_skills = excluded.missing_skills
        WHERE applications.status = 'discovered'
        """, (
            job.get("id"),
            job.get("company", "Unknown"),
            job.get("title", "Unknown"),
            job.get("location", ""),
            job.get("url", ""),
            job.get("contact_email", ""),
            job.get("source", "web"),
            job.get("description", ""),
            job.get("match_score", 0),
            json.dumps(job.get("matched_skills", [])),
            json.dumps(job.get("missing_skills", [])),
            job.get("notes", "")
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB Error] Could not save job {job.get('id')}: {e}")
        return False
    finally:
        conn.close()

def update_job_status(job_id: str, status: str, tailored_resume_path: str = None, notes: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    applied_at = datetime.utcnow().isoformat() if status == "applied" else None
    
    query = "UPDATE applications SET status = ?"
    params = [status]
    
    if tailored_resume_path:
        query += ", tailored_resume_path = ?"
        params.append(tailored_resume_path)
    if applied_at:
        query += ", applied_at = ?"
        params.append(applied_at)
    if notes:
        query += ", notes = ?"
        params.append(notes)
        
    query += " WHERE job_id = ?"
    params.append(job_id)
    
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()

def get_jobs_by_status(status: str = "discovered", min_score: int = 0, limit: int = 50):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM applications 
    WHERE status = ? AND match_score >= ?
    ORDER BY match_score DESC, created_at DESC
    LIMIT ?
    """, (status, min_score, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_applications():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications ORDER BY match_score DESC, created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
