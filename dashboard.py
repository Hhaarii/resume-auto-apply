import os
import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import DB_PATH, TAILORED_DIR, SEARCH_CONFIG
from modules.database import init_db, get_all_applications, get_jobs_by_status, update_job_status
from modules.resume_parser import load_or_create_master_profile
from modules.job_fetcher import fetch_all_jobs
from modules.matcher import analyze_job_match
from modules.tailor import tailor_resume, generate_cover_letter
from modules.pdf_generator import generate_pdf
from modules.applier import auto_fill_job_application
from modules.india_jobs import load_and_score_india_jobs
from modules.email_dispatcher import generate_cold_email, send_email_with_pdf_attachment, get_email_settings, save_email_settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Resume Auto-Updater & Application Co-Pilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def index():
    profile = load_or_create_master_profile()
    jobs = get_all_applications()
    
    # Calculate stats
    total_scanned = len(jobs)
    high_matches = len([j for j in jobs if (j.get("match_score") or 0) >= 60])
    tailored_count = len([j for j in jobs if j.get("status") == "tailored"])
    applied_count = len([j for j in jobs if j.get("status") == "applied"])

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Resume Auto-Updater & Job Application Co-Pilot</title>
      <style>
        :root {{
          --bg-main: #0f172a;
          --bg-card: #1e293b;
          --bg-card-hover: #334155;
          --border: #334155;
          --text-main: #f8fafc;
          --text-muted: #94a3b8;
          --accent: #38bdf8;
          --accent-hover: #0284c7;
          --success: #34d399;
          --warning: #fbbf24;
          --danger: #f87171;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background-color: var(--bg-main);
          color: var(--text-main);
          padding: 24px 32px;
        }}
        header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 20px;
          border-bottom: 1px solid var(--border);
          margin-bottom: 24px;
        }}
        .user-badge {{
          background: rgba(56, 189, 248, 0.1);
          border: 1px solid var(--accent);
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 13px;
          color: var(--accent);
          font-weight: 500;
        }}
        .stats-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-bottom: 28px;
        }}
        .stat-card {{
          background: var(--bg-card);
          border: 1px solid var(--border);
          padding: 16px 20px;
          border-radius: 12px;
        }}
        .stat-card .label {{ font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; color: var(--accent); }}
        
        .toolbar {{
          display: flex;
          gap: 12px;
          margin-bottom: 20px;
          flex-wrap: wrap;
        }}
        button.btn {{
          background: var(--accent);
          color: #0f172a;
          border: none;
          padding: 10px 18px;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 14px;
        }}
        button.btn:hover {{ background: var(--accent-hover); color: #fff; }}
        button.btn-secondary {{
          background: var(--bg-card);
          color: var(--text-main);
          border: 1px solid var(--border);
        }}
        button.btn-secondary:hover {{ background: var(--bg-card-hover); }}

        table {{
          width: 100%;
          border-collapse: collapse;
          background: var(--bg-card);
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid var(--border);
        }}
        th, td {{
          padding: 14px 16px;
          text-align: left;
          border-bottom: 1px solid var(--border);
          font-size: 13.5px;
        }}
        th {{ background: #182234; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.6px; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}
        
        .badge {{
          padding: 4px 10px;
          border-radius: 6px;
          font-weight: 700;
          font-size: 12px;
          display: inline-block;
        }}
        .badge-score-high {{ background: rgba(52, 211, 153, 0.15); color: var(--success); border: 1px solid rgba(52, 211, 153, 0.4); }}
        .badge-score-mid {{ background: rgba(56, 189, 248, 0.15); color: var(--accent); border: 1px solid rgba(56, 189, 248, 0.4); }}
        .badge-status {{ background: #334155; color: #cbd5e1; font-weight: 500; font-size: 11px; text-transform: uppercase; }}
        
        .tag {{
          background: #0f172a;
          color: #94a3b8;
          padding: 2px 7px;
          border-radius: 4px;
          font-size: 11px;
          margin-right: 4px;
          display: inline-block;
          margin-bottom: 3px;
        }}
        .tag-match {{ background: rgba(52, 211, 153, 0.1); color: var(--success); border: 1px solid rgba(52, 211, 153, 0.3); }}
        .tag-missing {{ background: rgba(248, 113, 113, 0.1); color: #fca5a5; }}

        .actions-cell {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .btn-action {{
          padding: 6px 12px;
          font-size: 12px;
          border-radius: 6px;
          cursor: pointer;
          border: 1px solid var(--border);
          background: #0f172a;
          color: var(--text-main);
          text-decoration: none;
          font-weight: 500;
        }}
        .btn-action:hover {{ background: var(--accent); color: #0f172a; border-color: var(--accent); }}
        .btn-apply {{ background: rgba(52, 211, 153, 0.15); color: var(--success); border-color: rgba(52, 211, 153, 0.4); }}
        .btn-apply:hover {{ background: var(--success); color: #0f172a; }}
      </style>
    </head>
    <body>

      <header>
        <div>
          <h2>Resume Auto-Updater & Job Application Co-Pilot</h2>
          <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">Candidate: <strong>{profile.get('name')}</strong> | {profile.get('location')}</p>
        </div>
        <div class="user-badge">Role: Robotics & Embedded Systems Engineer</div>
      </header>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="label">Total Vacancies Scanned</div>
          <div class="value">{total_scanned}</div>
        </div>
        <div class="stat-card">
          <div class="label">Top ATS Matches (&ge;60%)</div>
          <div class="value">{high_matches}</div>
        </div>
        <div class="stat-card">
          <div class="label">Tailored Resumes Ready</div>
          <div class="value">{tailored_count}</div>
        </div>
        <div class="stat-card">
          <div class="label">Applications Submitted</div>
          <div class="value">{applied_count}</div>
        </div>
      </div>

      <div class="toolbar">
        <button class="btn" onclick="triggerIndiaScan()">🇮🇳 Scan India Roles & HR Emails</button>
        <button class="btn btn-secondary" onclick="triggerScan()">Search Global Feeds</button>
        <button class="btn btn-secondary" onclick="triggerTailorAll()">Tailor All Top Matches</button>
        <button class="btn btn-secondary" onclick="openSettingsModal()">⚙️ Email Auto-Send Setup</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Match</th>
            <th>Role & Company</th>
            <th>Location</th>
            <th>HR Contact</th>
            <th>Matched Skills</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
    """

    for job in jobs[:40]:
        score = job.get("match_score", 0)
        badge_cls = "badge-score-high" if score >= 70 else "badge-score-mid"
        matched = json.loads(job.get("matched_skills") or "[]")
        missing = json.loads(job.get("missing_skills") or "[]")
        
        tags_html = "".join([f'<span class="tag tag-match">{m}</span>' for m in matched[:4]])
        if missing:
            tags_html += "".join([f'<span class="tag tag-missing">+{m}</span>' for m in missing[:2]])

        job_id = job.get("job_id")
        status = job.get("status", "discovered")
        has_pdf = bool(job.get("tailored_resume_path"))
        apply_url = job.get("url", "#")
        contact_email = job.get("contact_email") or ""

        email_html = f'<span style="color: var(--accent); font-size: 12px; font-weight: 500;">{contact_email}</span>' if contact_email else '<span style="color: var(--text-muted); font-size: 11px;">Direct Portal</span>'

        actions_html = f'<a href="{apply_url}" target="_blank" class="btn-action">Link</a>'
        if contact_email:
            if status == "applied":
                actions_html += '<span class="badge" style="background: rgba(52, 211, 153, 0.2); color: var(--success); font-size: 11px;">✅ Applied</span>'
            else:
                actions_html += f'<button class="btn-action btn-apply" onclick="sendDirectEmail(\'{job_id}\', this)">🚀 Direct Send + PDF</button>'
        
        if has_pdf:
            actions_html += f'<a href="/api/resume/{job_id}" target="_blank" class="btn-action">PDF</a>'
        else:
            actions_html += f'<button class="btn-action" onclick="tailorJob(\'{job_id}\')">Tailor</button>'
        
        if not contact_email:
            actions_html += f'<button class="btn-action" onclick="applyJob(\'{job_id}\')">Auto-Fill</button>'

        html += f"""
          <tr>
            <td><span class="badge {badge_cls}">{score}%</span></td>
            <td>
              <div style="font-weight: 600;">{job.get('title')}</div>
              <div style="color: var(--text-muted); font-size: 12px;">{job.get('company')} &bull; {job.get('source')}</div>
            </td>
            <td>{job.get('location', 'Remote')}</td>
            <td>{email_html}</td>
            <td>{tags_html}</td>
            <td><span class="badge badge-status">{status}</span></td>
            <td class="actions-cell">{actions_html}</td>
          </tr>
        """

    html += """
        </tbody>
      </table>

      <script>
        async function triggerIndiaScan() {
          const btn = event.target;
          btn.innerText = "Loading India HR contacts...";
          btn.disabled = true;
          try {
            const res = await fetch("/api/scan-india", { method: "POST" });
            const data = await res.json();
            alert("Loaded " + data.count + " verified Indian companies & HR emails!");
            window.location.reload();
          } catch(e) {
            alert("Error: " + e);
          } finally {
            btn.innerText = "🇮🇳 Scan India Roles & HR Emails";
            btn.disabled = false;
          }
        }

        async function triggerScan() {
          const btn = event.target;
          btn.innerText = "Scanning live jobs...";
          btn.disabled = true;
          try {
            const res = await fetch("/api/scan", { method: "POST" });
            const data = await res.json();
            alert("Scan completed! Found " + data.matched + " positions.");
            window.location.reload();
          } catch(e) {
            alert("Scan error: " + e);
          } finally {
            btn.innerText = "Search & Scan New Jobs";
            btn.disabled = false;
          }
        }

        async function triggerTailorAll() {
          const btn = event.target;
          btn.innerText = "Tailoring...";
          btn.disabled = true;
          try {
            await fetch("/api/tailor-all", { method: "POST" });
            alert("Top resumes tailored and compiled to PDF!");
            window.location.reload();
          } catch(e) {
            alert("Error: " + e);
          } finally {
            btn.innerText = "Tailor Top Matches";
            btn.disabled = false;
          }
        }

        async function tailorJob(jobId) {
          try {
            await fetch("/api/tailor/" + jobId, { method: "POST" });
            alert("Resume tailored and PDF generated!");
            window.location.reload();
          } catch(e) {
            alert("Error: " + e);
          }
        }

        async function applyJob(jobId) {
          if (!confirm("This will launch the Co-Pilot browser to pre-fill the application with your tailored resume. Ready?")) return;
          try {
            fetch("/api/apply/" + jobId, { method: "POST" });
            alert("Co-Pilot launched! Check your browser window to review and submit.");
          } catch(e) {
            alert("Error: " + e);
          }
        }
        function openSettingsModal() {
          document.getElementById('settingsModal').style.display = 'flex';
          fetch('/api/settings/email').then(r => r.json()).then(data => {
            if (data.sender_email) document.getElementById('smtpEmail').value = data.sender_email;
            if (data.sender_password) document.getElementById('smtpPassword').value = data.sender_password;
          });
        }

        function closeSettingsModal() {
          document.getElementById('settingsModal').style.display = 'none';
        }

        async function saveEmailSettings() {
          const email = document.getElementById('smtpEmail').value;
          const password = document.getElementById('smtpPassword').value;
          await fetch('/api/settings/email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sender_email: email, sender_password: password })
          });
          alert('Email settings saved securely!');
          closeSettingsModal();
        }

        function openMailClientWithResume(jobId, mailtoUrl) {
          // 1. Immediately download tailored PDF onto device so it is ready to attach
          const a = document.createElement('a');
          a.href = '/api/resume/' + jobId;
          a.download = '';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);

          // 2. Open pre-filled email client
          setTimeout(() => {
            window.location.href = mailtoUrl;
          }, 350);
        }

        async function sendDirectEmail(jobId, btn) {
          if (!confirm("Directly send email with your tailored PDF resume attached to HR?")) return;
          const origText = btn ? btn.innerText : "";
          if (btn) {
            btn.innerText = "Attaching & Sending...";
            btn.disabled = true;
          }
          try {
            const res = await fetch('/api/send-email-direct/' + jobId, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
              alert(data.message);
              window.location.reload();
            } else {
              if (data.error && data.error.includes("password not configured")) {
                alert("Please enter your Gmail App Password once in Email Setup so the system can silently attach and deliver your resume.");
                openSettingsModal();
              } else {
                alert("Notice: " + data.error);
              }
              if (btn) {
                btn.innerText = origText;
                btn.disabled = false;
              }
            }
          } catch(e) {
            alert("Error sending email: " + e);
            if (btn) {
              btn.innerText = origText;
              btn.disabled = false;
            }
          }
        }
      </script>

      <!-- Settings Modal -->
      <div id="settingsModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: var(--bg-card); border: 1px solid var(--border); padding: 24px; border-radius: 12px; width: 440px; max-width: 90%;">
          <h3 style="margin-bottom: 12px; color: var(--accent);">⚙️ Email Auto-Send Setup</h3>
          <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
            Configure your Gmail App Password once to enable <strong>1-Click Direct Sending with your tailored PDF automatically attached</strong>!
          </p>
          <div style="margin-bottom: 12px;">
            <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px;">Your Email (Gmail)</label>
            <input id="smtpEmail" type="email" value="{profile.get('email')}" style="width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid var(--border); color: #fff; border-radius: 6px; font-size: 13px;">
          </div>
          <div style="margin-bottom: 16px;">
            <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px;">Gmail 16-character App Password (<a href="https://myaccount.google.com/apppasswords" target="_blank" style="color: var(--accent);">Generate here</a>)</label>
            <input id="smtpPassword" type="password" placeholder="e.g. abcd efgh ijkl mnop" style="width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid var(--border); color: #fff; border-radius: 6px; font-size: 13px;">
            <span style="font-size: 11px; color: var(--text-muted); margin-top: 4px; display: block;">Saved locally on your machine in data/email_settings.json</span>
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 8px;">
            <button class="btn btn-secondary" onclick="closeSettingsModal()">Cancel</button>
            <button class="btn" onclick="saveEmailSettings()">Save Settings</button>
          </div>
        </div>
      </div>
    </body>
    </html>
    """
    return html

@app.post("/api/scan-india")
def api_scan_india():
    jobs = load_and_score_india_jobs()
    return {"status": "ok", "count": len(jobs)}

@app.post("/api/scan")
def api_scan():
    profile = load_or_create_master_profile()
    jobs = fetch_all_jobs()
    count = 0
    for job in jobs:
        score, matched_skills, missing_skills = analyze_job_match(job, profile)
        job["match_score"] = score
        job["matched_skills"] = matched_skills
        job["missing_skills"] = missing_skills
        from modules.database import save_or_update_job
        save_or_update_job(job)
        if score >= 60:
            count += 1
    return {"status": "ok", "matched": count, "total": len(jobs)}

@app.post("/api/tailor/{job_id}")
def api_tailor_job(job_id: str):
    profile = load_or_create_master_profile()
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    matched_skills = json.loads(job.get("matched_skills") or "[]")
    tailored_data = tailor_resume(profile, job, matched_skills)
    pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))
    update_job_status(job_id, "tailored", str(pdf_path))
    return {"status": "ok", "pdf": str(pdf_path.name)}

@app.post("/api/tailor-all")
def api_tailor_all():
    profile = load_or_create_master_profile()
    top_jobs = get_jobs_by_status("discovered", min_score=60, limit=5)
    for job in top_jobs:
        matched_skills = json.loads(job.get("matched_skills") or "[]")
        tailored_data = tailor_resume(profile, job, matched_skills)
        pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))
        update_job_status(job.get("job_id"), "tailored", str(pdf_path))
    return {"status": "ok", "tailored_count": len(top_jobs)}

@app.get("/api/resume/{job_id}")
def api_get_resume_pdf(job_id: str):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT tailored_resume_path FROM applications WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row["tailored_resume_path"]:
        raise HTTPException(status_code=404, detail="Tailored PDF not generated yet")
    pdf_path = Path(row["tailored_resume_path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)

@app.post("/api/apply/{job_id}")
def api_apply(job_id: str):
    profile = load_or_create_master_profile()
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    pdf_path = Path(job.get("tailored_resume_path") or "")
    if not pdf_path.exists():
        matched_skills = json.loads(job.get("matched_skills") or "[]")
        tailored_data = tailor_resume(profile, job, matched_skills)
        pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))
        update_job_status(job_id, "tailored", str(pdf_path))
    
    # Launch in background thread
    import threading
    t = threading.Thread(target=auto_fill_job_application, args=(job, profile, pdf_path))
    t.start()
    return {"status": "launched", "job": job.get("title")}

@app.get("/api/settings/email")
def api_get_email_settings():
    return get_email_settings()

@app.post("/api/settings/email")
def api_save_email_settings(request_data: dict):
    save_email_settings(request_data)
    return {"status": "ok"}

@app.post("/api/send-email-direct/{job_id}")
def api_send_email_direct(job_id: str):
    profile = load_or_create_master_profile()
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    
    # Ensure tailored PDF exists
    pdf_path = Path(job.get("tailored_resume_path") or "")
    if not pdf_path.exists():
        matched_skills = json.loads(job.get("matched_skills") or "[]")
        tailored_data = tailor_resume(profile, job, matched_skills)
        pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))
        update_job_status(job_id, "tailored", str(pdf_path))

    draft = generate_cold_email(profile, job)
    res = send_email_with_pdf_attachment(
        recipient_email=job.get("contact_email"),
        subject=draft.get("subject"),
        body=draft.get("body"),
        pdf_path=pdf_path
    )
    if res.get("success"):
        update_job_status(job_id, "applied", str(pdf_path), f"Direct email + PDF sent to {job.get('contact_email')}")
    return res

if __name__ == "__main__":
    import argparse
    import socket
    parser = argparse.ArgumentParser(description="Resume Auto-Apply Dashboard")
    parser.add_argument("--public", action="store_true", help="Generate public HTTPS URL accessible from anywhere")
    args = parser.parse_args()

    local_ip = "192.168.1.47"
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        pass

    print("\n" + "="*65)
    print("   RESUME AUTO-UPDATER & APPLICATION CO-PILOT DASHBOARD")
    print("="*65)
    print(" [*] This Computer:       http://localhost:8000")
    print(f" [*] On Your Phone/Wi-Fi:  http://{local_ip}:8000")
    print(" [*] For Worldwide Link:  Run 'share_public.bat' (100% Free HTTPS)")
    print("="*65 + "\n")
    uvicorn.run("dashboard:app", host="0.0.0.0", port=8000, reload=False)
