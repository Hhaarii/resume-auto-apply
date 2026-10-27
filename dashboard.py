import os
import sys
import json
import threading
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

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

# ─── Background Scheduler ───────────────────────────────────────────────────
from apscheduler.schedulers.background import BackgroundScheduler

_last_refresh = {"time": None}

def scheduled_scan():
    """Auto-refresh job openings every 6 hours."""
    try:
        from modules.database import save_or_update_job
        profile = load_or_create_master_profile()
        # Fetch global jobs
        jobs = fetch_all_jobs()
        for job in jobs:
            score, matched_skills, missing_skills = analyze_job_match(job, profile)
            job["match_score"] = score
            job["matched_skills"] = matched_skills
            job["missing_skills"] = missing_skills
            save_or_update_job(job)
        # Also reload India jobs
        load_and_score_india_jobs()
        _last_refresh["time"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
        print(f"[Scheduler] Auto-refresh done — {len(jobs)} jobs fetched at {_last_refresh['time']}")
    except Exception as e:
        print(f"[Scheduler] Error during auto-refresh: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_scan, "interval", hours=6, id="auto_refresh")

# ─── App Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    print("[Scheduler] Auto-refresh every 6 hours started.")
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(title="Resume Auto-Updater & Application Co-Pilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Dashboard ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    profile = load_or_create_master_profile()
    jobs = get_all_applications()

    # Separate active vs applied
    active_jobs  = [j for j in jobs if j.get("status") != "applied"]
    applied_jobs = [j for j in jobs if j.get("status") == "applied"]

    total_scanned  = len(jobs)
    high_matches   = len([j for j in jobs if (j.get("match_score") or 0) >= 60])
    tailored_count = len([j for j in jobs if j.get("status") == "tailored"])
    applied_count  = len(applied_jobs)
    last_refresh   = _last_refresh["time"] or "Not yet refreshed this session"

    def render_rows(job_list, show_send_btn=True):
        rows = ""
        for job in job_list[:60]:
            score     = job.get("match_score", 0)
            badge_cls = "badge-score-high" if score >= 70 else "badge-score-mid"
            matched   = json.loads(job.get("matched_skills") or "[]")
            missing   = json.loads(job.get("missing_skills") or "[]")

            tags_html = "".join([f'<span class="tag tag-match">{m}</span>' for m in matched[:4]])
            if missing:
                tags_html += "".join([f'<span class="tag tag-missing">+{m}</span>' for m in missing[:2]])

            job_id        = job.get("job_id")
            status        = job.get("status", "discovered")
            has_pdf       = bool(job.get("tailored_resume_path"))
            apply_url     = job.get("url", "#")
            contact_email = job.get("contact_email") or ""
            applied_on    = job.get("applied_at", "")

            email_html = (
                f'<span style="color: var(--accent); font-size: 12px; font-weight: 500;">{contact_email}</span>'
                if contact_email else
                '<span style="color: var(--text-muted); font-size: 11px;">Direct Portal</span>'
            )

            actions_html = f'<a href="{apply_url}" target="_blank" class="btn-action">Link</a>'

            if contact_email:
                if status == "applied":
                    actions_html += '<span class="badge" style="background: rgba(52,211,153,0.2); color: var(--success); font-size: 11px;">Applied</span>'
                elif show_send_btn:
                    # "Open in Gmail" button — downloads PDF + opens Gmail compose
                    actions_html += (
                        f'<button class="btn-action" style="background:rgba(251,191,36,0.15);color:#fbbf24;border-color:rgba(251,191,36,0.4);" '
                        f'onclick="openInGmail(\'{job_id}\', this)">&#128233; Preview &amp; Send</button>'
                    )

            if has_pdf:
                actions_html += f'<a href="/api/resume/{job_id}" target="_blank" class="btn-action">PDF</a>'
            else:
                actions_html += f'<button class="btn-action" onclick="tailorJob(\'{job_id}\')">Tailor</button>'

            if not contact_email:
                actions_html += f'<button class="btn-action" onclick="applyJob(\'{job_id}\')">Auto-Fill</button>'

            date_cell = f'<td style="font-size:11px;color:var(--text-muted);">{applied_on[:10] if applied_on else "—"}</td>' if not show_send_btn else ""

            rows += f"""
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
            {date_cell}
            <td class="actions-cell">{actions_html}</td>
          </tr>
            """
        return rows

    active_rows  = render_rows(active_jobs,  show_send_btn=True)
    applied_rows = render_rows(applied_jobs, show_send_btn=False)

    # Extra "Date Applied" column header only on Applied tab
    active_thead  = "<th>Match</th><th>Role &amp; Company</th><th>Location</th><th>HR Contact</th><th>Matched Skills</th><th>Status</th><th>Actions</th>"
    applied_thead = "<th>Match</th><th>Role &amp; Company</th><th>Location</th><th>HR Contact</th><th>Matched Skills</th><th>Status</th><th>Date Applied</th><th>Actions</th>"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Resume Auto-Updater &amp; Job Application Co-Pilot</title>
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
          display: flex; justify-content: space-between; align-items: center;
          padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px;
        }}
        .user-badge {{
          background: rgba(56,189,248,0.1); border: 1px solid var(--accent);
          padding: 6px 14px; border-radius: 20px; font-size: 13px;
          color: var(--accent); font-weight: 500;
        }}
        .refresh-badge {{
          font-size: 11px; color: var(--text-muted); margin-top: 4px;
        }}
        .stats-grid {{
          display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px; margin-bottom: 28px;
        }}
        .stat-card {{
          background: var(--bg-card); border: 1px solid var(--border);
          padding: 16px 20px; border-radius: 12px;
        }}
        .stat-card .label {{ font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; color: var(--accent); }}

        .toolbar {{
          display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
        }}
        button.btn {{
          background: var(--accent); color: #0f172a; border: none;
          padding: 10px 18px; border-radius: 8px; font-weight: 600;
          cursor: pointer; transition: all 0.2s;
          display: inline-flex; align-items: center; gap: 6px; font-size: 14px;
        }}
        button.btn:hover {{ background: var(--accent-hover); color: #fff; }}
        button.btn-secondary {{
          background: var(--bg-card); color: var(--text-main);
          border: 1px solid var(--border);
        }}
        button.btn-secondary:hover {{ background: var(--bg-card-hover); }}

        /* ─── Tabs ──────────────────────────────────────── */
        .tab-bar {{
          display: flex; gap: 0; margin-bottom: 0;
          border-bottom: 2px solid var(--border);
        }}
        .tab-btn {{
          padding: 10px 24px; background: none; border: none;
          color: var(--text-muted); font-size: 14px; font-weight: 600;
          cursor: pointer; border-bottom: 2px solid transparent;
          margin-bottom: -2px; transition: all 0.2s;
        }}
        .tab-btn.active {{
          color: var(--accent); border-bottom-color: var(--accent);
        }}
        .tab-btn:hover {{ color: var(--text-main); }}
        .tab-panel {{ display: none; padding-top: 16px; }}
        .tab-panel.active {{ display: block; }}
        .applied-count-badge {{
          background: rgba(52,211,153,0.15); color: var(--success);
          border-radius: 10px; padding: 1px 8px; font-size: 12px;
          margin-left: 6px; font-weight: 700;
        }}

        table {{
          width: 100%; border-collapse: collapse;
          background: var(--bg-card); border-radius: 12px;
          overflow: hidden; border: 1px solid var(--border);
        }}
        th, td {{
          padding: 14px 16px; text-align: left;
          border-bottom: 1px solid var(--border); font-size: 13.5px;
        }}
        th {{ background: #182234; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.6px; }}
        tr:hover td {{ background: rgba(255,255,255,0.02); }}

        .badge {{
          padding: 4px 10px; border-radius: 6px; font-weight: 700;
          font-size: 12px; display: inline-block;
        }}
        .badge-score-high {{ background: rgba(52,211,153,0.15); color: var(--success); border: 1px solid rgba(52,211,153,0.4); }}
        .badge-score-mid  {{ background: rgba(56,189,248,0.15); color: var(--accent); border: 1px solid rgba(56,189,248,0.4); }}
        .badge-status {{ background: #334155; color: #cbd5e1; font-weight: 500; font-size: 11px; text-transform: uppercase; }}

        .tag {{
          background: #0f172a; color: #94a3b8;
          padding: 2px 7px; border-radius: 4px; font-size: 11px;
          margin-right: 4px; display: inline-block; margin-bottom: 3px;
        }}
        .tag-match   {{ background: rgba(52,211,153,0.1); color: var(--success); border: 1px solid rgba(52,211,153,0.3); }}
        .tag-missing {{ background: rgba(248,113,113,0.1); color: #fca5a5; }}

        .actions-cell {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .btn-action {{
          padding: 6px 12px; font-size: 12px; border-radius: 6px;
          cursor: pointer; border: 1px solid var(--border);
          background: #0f172a; color: var(--text-main);
          text-decoration: none; font-weight: 500;
        }}
        .btn-action:hover {{ background: var(--accent); color: #0f172a; border-color: var(--accent); }}

        /* Toast */
        #toast {{
          position: fixed; bottom: 24px; right: 24px; z-index: 9999;
          background: #1e293b; border: 1px solid var(--success);
          color: var(--success); padding: 12px 20px; border-radius: 10px;
          font-size: 13px; font-weight: 600; display: none;
          box-shadow: 0 4px 24px rgba(0,0,0,0.5);
        }}
      </style>
    </head>
    <body>

      <header>
        <div>
          <h2>Resume Auto-Updater &amp; Job Application Co-Pilot</h2>
          <p style="color: var(--text-muted); font-size: 14px; margin-top: 4px;">
            Candidate: <strong>{profile.get('name')}</strong> | {profile.get('location')}
          </p>
          <div class="refresh-badge">&#128337; Auto-refresh every 6 hrs &nbsp;|&nbsp; Last refresh: <span id="lastRefreshTime">{last_refresh}</span></div>
        </div>
        <div class="user-badge">Role: Robotics &amp; Embedded Systems Engineer</div>
      </header>

      <div class="stats-grid">
        <div class="stat-card"><div class="label">Total Vacancies Scanned</div><div class="value">{total_scanned}</div></div>
        <div class="stat-card"><div class="label">Top ATS Matches (&ge;60%)</div><div class="value">{high_matches}</div></div>
        <div class="stat-card"><div class="label">Tailored Resumes Ready</div><div class="value">{tailored_count}</div></div>
        <div class="stat-card"><div class="label">Applications Submitted</div><div class="value" style="color: var(--success);">{applied_count}</div></div>
      </div>

      <div class="toolbar">
        <button class="btn" onclick="triggerIndiaScan()">&#127470;&#127475; Scan India Roles &amp; HR Emails</button>
        <button class="btn btn-secondary" onclick="triggerScan()">Search Global Feeds</button>
        <button class="btn btn-secondary" onclick="triggerTailorAll()">Tailor All Top Matches</button>
        <button class="btn btn-secondary" onclick="openSettingsModal()">&#9881;&#65039; Email Auto-Send Setup</button>
      </div>

      <!-- Tab Bar -->
      <div class="tab-bar">
        <button class="tab-btn active" onclick="switchTab('active', this)">Active Matches</button>
        <button class="tab-btn" onclick="switchTab('applied', this)">
          Applied Jobs <span class="applied-count-badge">{applied_count}</span>
        </button>
      </div>

      <!-- Active Jobs Tab -->
      <div id="tab-active" class="tab-panel active">
        <table>
          <thead><tr>{active_thead}</tr></thead>
          <tbody>{active_rows}</tbody>
        </table>
      </div>

      <!-- Applied Jobs Tab -->
      <div id="tab-applied" class="tab-panel">
        {"<p style='color:var(--text-muted);padding:24px;text-align:center;'>No applications sent yet. Use Preview &amp; Send on the Active Matches tab.</p>" if not applied_jobs else f"<table><thead><tr>{applied_thead}</tr></thead><tbody>{applied_rows}</tbody></table>"}
      </div>

      <!-- Toast notification -->
      <div id="toast"></div>

      <script>
        // ─── Tab Switching ──────────────────────────────────────────────
        function switchTab(name, btn) {{
          document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
          document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          document.getElementById('tab-' + name).classList.add('active');
          btn.classList.add('active');
        }}

        // ─── Toast ──────────────────────────────────────────────────────
        function showToast(msg, duration=4500) {{
          const t = document.getElementById('toast');
          t.textContent = msg;
          t.style.display = 'block';
          setTimeout(() => t.style.display = 'none', duration);
        }}

        // ─── Open In Gmail (downloads PDF + opens Gmail compose) ────────
        async function openInGmail(jobId, btn) {{
          const origText = btn ? btn.innerHTML : '';
          if (btn) {{ btn.innerHTML = 'Loading...'; btn.disabled = true; }}
          try {{
            // 1. Load preview data (also auto-generates PDF)
            const res = await fetch('/api/preview-email/' + jobId);
            if (!res.ok) throw new Error('Could not load email preview');
            const data = await res.json();

            // 2. Download the tailored PDF to device
            const a = document.createElement('a');
            a.href = '/api/resume/' + jobId;
            a.download = data.pdf_name || 'Resume_Hariprasad.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            // 3. After short delay, open Gmail compose pre-filled
            setTimeout(() => {{
              const gmailUrl = 'https://mail.google.com/mail/?view=cm&fs=1' +
                '&to=' + encodeURIComponent(data.to) +
                '&su=' + encodeURIComponent(data.subject) +
                '&body=' + encodeURIComponent(data.body);
              window.open(gmailUrl, '_blank');

              showToast('Resume downloaded to Downloads folder — attach it in the Gmail window!');
            }}, 500);

            // 4. Mark job as applied in background
            fetch('/api/mark-applied/' + jobId, {{ method: 'POST' }});

          }} catch(e) {{
            alert('Error: ' + e);
          }} finally {{
            if (btn) {{ btn.innerHTML = origText; btn.disabled = false; }}
          }}
        }}

        // ─── Scans ──────────────────────────────────────────────────────
        async function triggerIndiaScan() {{
          const btn = event.target;
          btn.innerText = 'Loading India HR contacts...';
          btn.disabled = true;
          try {{
            const res = await fetch('/api/scan-india', {{ method: 'POST' }});
            const data = await res.json();
            alert('Loaded ' + data.count + ' verified Indian companies & HR emails!');
            window.location.reload();
          }} catch(e) {{ alert('Error: ' + e); }}
          finally {{ btn.innerText = '&#127470;&#127475; Scan India Roles & HR Emails'; btn.disabled = false; }}
        }}

        async function triggerScan() {{
          const btn = event.target;
          btn.innerText = 'Scanning live jobs...';
          btn.disabled = true;
          try {{
            const res = await fetch('/api/scan', {{ method: 'POST' }});
            const data = await res.json();
            alert('Scan completed! Found ' + data.matched + ' positions.');
            window.location.reload();
          }} catch(e) {{ alert('Scan error: ' + e); }}
          finally {{ btn.innerText = 'Search Global Feeds'; btn.disabled = false; }}
        }}

        async function triggerTailorAll() {{
          const btn = event.target;
          btn.innerText = 'Tailoring...';
          btn.disabled = true;
          try {{
            await fetch('/api/tailor-all', {{ method: 'POST' }});
            alert('Top resumes tailored and compiled to PDF!');
            window.location.reload();
          }} catch(e) {{ alert('Error: ' + e); }}
          finally {{ btn.innerText = 'Tailor All Top Matches'; btn.disabled = false; }}
        }}

        async function tailorJob(jobId) {{
          try {{
            await fetch('/api/tailor/' + jobId, {{ method: 'POST' }});
            alert('Resume tailored and PDF generated!');
            window.location.reload();
          }} catch(e) {{ alert('Error: ' + e); }}
        }}

        async function applyJob(jobId) {{
          if (!confirm('This will launch the Co-Pilot browser to pre-fill the application. Ready?')) return;
          try {{
            fetch('/api/apply/' + jobId, {{ method: 'POST' }});
            alert('Co-Pilot launched! Check your browser window to review and submit.');
          }} catch(e) {{ alert('Error: ' + e); }}
        }}

        // ─── Settings Modal ──────────────────────────────────────────────
        function openSettingsModal() {{
          document.getElementById('settingsModal').style.display = 'flex';
          fetch('/api/settings/email').then(r => r.json()).then(data => {{
            if (data.sender_email)    document.getElementById('smtpEmail').value = data.sender_email;
            if (data.sender_password) document.getElementById('smtpPassword').value = data.sender_password;
          }});
        }}
        function closeSettingsModal() {{ document.getElementById('settingsModal').style.display = 'none'; }}
        async function saveEmailSettings() {{
          const email    = document.getElementById('smtpEmail').value;
          const password = document.getElementById('smtpPassword').value;
          await fetch('/api/settings/email', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ sender_email: email, sender_password: password }})
          }});
          alert('Email settings saved!');
          closeSettingsModal();
        }}
      </script>

      <!-- Settings Modal -->
      <div id="settingsModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:1000;align-items:center;justify-content:center;">
        <div style="background:var(--bg-card);border:1px solid var(--border);padding:24px;border-radius:12px;width:440px;max-width:90%;">
          <h3 style="margin-bottom:12px;color:var(--accent);">&#9881;&#65039; Email Auto-Send Setup</h3>
          <p style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">
            Configure your Gmail App Password once to enable direct sending.
          </p>
          <div style="margin-bottom:12px;">
            <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Your Email (Gmail)</label>
            <input id="smtpEmail" type="email" value="{profile.get('email','')}" style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid var(--border);color:#fff;border-radius:6px;font-size:13px;">
          </div>
          <div style="margin-bottom:16px;">
            <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">
              Gmail 16-char App Password (<a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:var(--accent);">Generate here</a>)
            </label>
            <input id="smtpPassword" type="password" placeholder="e.g. abcd efgh ijkl mnop"
              style="width:100%;padding:8px 12px;background:#0f172a;border:1px solid var(--border);color:#fff;border-radius:6px;font-size:13px;">
            <span style="font-size:11px;color:var(--text-muted);margin-top:4px;display:block;">Saved locally in data/email_settings.json</span>
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;">
            <button class="btn btn-secondary" onclick="closeSettingsModal()">Cancel</button>
            <button class="btn" onclick="saveEmailSettings()">Save Settings</button>
          </div>
        </div>
      </div>

    </body>
    </html>
    """
    return html


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/scan-india")
def api_scan_india():
    jobs = load_and_score_india_jobs()
    _last_refresh["time"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return {"status": "ok", "count": len(jobs)}

@app.post("/api/scan")
def api_scan():
    from modules.database import save_or_update_job
    profile = load_or_create_master_profile()
    jobs = fetch_all_jobs()
    count = 0
    for job in jobs:
        score, matched_skills, missing_skills = analyze_job_match(job, profile)
        job["match_score"] = score
        job["matched_skills"] = matched_skills
        job["missing_skills"] = missing_skills
        save_or_update_job(job)
        if score >= 60:
            count += 1
    _last_refresh["time"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
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
    t = threading.Thread(target=auto_fill_job_application, args=(job, profile, pdf_path))
    t.start()
    return {"status": "launched", "job": job.get("title")}

@app.post("/api/mark-applied/{job_id}")
def api_mark_applied(job_id: str):
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
    update_job_status(job_id, "applied", job.get("tailored_resume_path", ""), f"Drafted in Gmail to {job.get('contact_email')}")
    return {"status": "ok"}

@app.get("/api/settings/email")
def api_get_email_settings():
    return get_email_settings()

@app.post("/api/settings/email")
def api_save_email_settings(request_data: dict):
    save_email_settings(request_data)
    return {"status": "ok"}

@app.get("/api/preview-email/{job_id}")
def api_preview_email(job_id: str):
    """Returns pre-filled email draft data so user can open Gmail compose with it."""
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

    # Auto-generate PDF if not yet done
    pdf_path = Path(job.get("tailored_resume_path") or "")
    if not pdf_path.exists():
        matched_skills = json.loads(job.get("matched_skills") or "[]")
        tailored_data = tailor_resume(profile, job, matched_skills)
        pdf_path = generate_pdf(tailored_data, job.get("company"), job.get("title"))
        update_job_status(job_id, "tailored", str(pdf_path))

    draft = generate_cold_email(profile, job)
    return {
        "to":       job.get("contact_email", ""),
        "subject":  draft.get("subject", ""),
        "body":     draft.get("body", ""),
        "pdf_name": pdf_path.name if pdf_path.exists() else "Resume PDF (will be auto-generated)",
        "job_id":   job_id
    }

@app.post("/api/send-email-direct/{job_id}")
async def api_send_email_direct(job_id: str, request: Request):
    profile = load_or_create_master_profile()
    import sqlite3
    try:
        override = await request.json()
    except Exception:
        override = {}
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

    draft = generate_cold_email(profile, job)
    subject = override.get("subject") or draft.get("subject")
    body    = override.get("body")    or draft.get("body")

    res = send_email_with_pdf_attachment(
        recipient_email=job.get("contact_email"),
        subject=subject,
        body=body,
        pdf_path=pdf_path
    )
    if res.get("success"):
        update_job_status(job_id, "applied", str(pdf_path), f"Direct email + PDF sent to {job.get('contact_email')}")
    return res

# ─── Scheduler manual trigger endpoint ──────────────────────────────────────
@app.post("/api/refresh-now")
def api_refresh_now():
    """Manually trigger a job refresh right now."""
    t = threading.Thread(target=scheduled_scan)
    t.start()
    return {"status": "ok", "message": "Refresh started in background"}

# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import socket
    parser = argparse.ArgumentParser(description="Resume Auto-Apply Dashboard")
    parser.add_argument("--public", action="store_true", help="Generate public HTTPS URL via cloudflared")
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
    print(" [*] For Worldwide Link:  Run 'share_public.bat' (Free HTTPS)")
    print(" [*] Auto-refresh:        Every 6 hours (background scheduler)")
    print("="*65 + "\n")

    uvicorn.run("dashboard:app", host="0.0.0.0", port=8000, reload=False)
