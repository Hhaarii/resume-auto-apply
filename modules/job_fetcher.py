import re
import requests
import html
from typing import List, Dict
from config import JOB_APIS, SEARCH_CONFIG

def clean_html(raw_html: str) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    clean = re.sub(r"<[^>]+>", " ", text)
    return " ".join(clean.split())

def fetch_remoteok_jobs(limit: int = 50) -> List[Dict]:
    """Fetches vacancies from RemoteOK API."""
    jobs = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    endpoints = [
        "https://remoteok.com/api?tag=engineer",
        "https://remoteok.com/api?tag=python",
        "https://remoteok.com/api?tag=hardware"
    ]
    for url in endpoints:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data[1:30]:
                    if isinstance(item, dict) and item.get("id"):
                        jobs.append({
                            "id": f"remoteok_{item.get('id', '')}",
                            "title": item.get("position", ""),
                            "company": item.get("company", ""),
                            "location": item.get("location", "Remote"),
                            "url": item.get("url", item.get("apply_url", "")),
                            "description": clean_html(item.get("description", "")),
                            "tags": item.get("tags", []),
                            "source": "RemoteOK"
                        })
        except Exception as e:
            print(f"[RemoteOK Error] {e}")
    return jobs

def fetch_jobicy_jobs(limit: int = 40) -> List[Dict]:
    """Fetches vacancies from Jobicy API."""
    jobs = []
    endpoints = [
        "https://jobicy.com/api/v2/remote-jobs?count=40&tag=engineering",
        "https://jobicy.com/api/v2/remote-jobs?count=40&tag=python"
    ]
    for url in endpoints:
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("jobs", [])
                for item in items:
                    if isinstance(item, dict) and item.get("id"):
                        jobs.append({
                            "id": f"jobicy_{item.get('id', '')}",
                            "title": item.get("jobTitle", ""),
                            "company": item.get("companyName", ""),
                            "location": item.get("jobGeo", "Remote"),
                            "url": item.get("url", ""),
                            "description": clean_html(item.get("jobDescription", "")),
                            "tags": [item.get("jobIndustry", "")] + (item.get("jobSkills") or []),
                            "source": "Jobicy"
                        })
        except Exception as e:
            print(f"[Jobicy Error] {e}")
    return jobs

def fetch_arbeitnow_jobs(limit: int = 30) -> List[Dict]:
    """Fetches vacancies from Arbeitnow API."""
    jobs = []
    try:
        resp = requests.get(JOB_APIS["arbeitnow"], timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            for item in items[:limit]:
                jobs.append({
                    "id": f"arbeitnow_{item.get('slug', '')}",
                    "title": item.get("title", ""),
                    "company": item.get("company_name", ""),
                    "location": item.get("location", "Remote"),
                    "url": item.get("url", ""),
                    "description": clean_html(item.get("description", "")),
                    "tags": item.get("tags", []),
                    "source": "Arbeitnow"
                })
    except Exception as e:
        print(f"[Arbeitnow Error] {e}")
    return jobs

def fetch_all_jobs() -> List[Dict]:
    """Aggregates jobs across all enabled sources and applies basic keyword pre-filtering."""
    all_raw_jobs = []
    print("[*] Fetching live vacancies from RemoteOK, Jobicy, and Arbeitnow...")
    
    all_raw_jobs.extend(fetch_remoteok_jobs())
    all_raw_jobs.extend(fetch_jobicy_jobs())
    all_raw_jobs.extend(fetch_arbeitnow_jobs())
    
    print(f"[*] Retrieved {len(all_raw_jobs)} total listings. Filtering by profile criteria...")
    
    filtered_jobs = []
    target_roles = [r.lower() for r in SEARCH_CONFIG.get("target_roles", [])]
    exclude = [x.lower() for x in SEARCH_CONFIG.get("exclude_keywords", [])]

    for job in all_raw_jobs:
        title = str(job.get("title", "")).lower()
        desc = str(job.get("description", "")).lower()
        
        # Flatten tags safely
        raw_tags = job.get("tags", [])
        clean_tag_list = []
        if isinstance(raw_tags, list):
            for t in raw_tags:
                if isinstance(t, str):
                    clean_tag_list.append(t.lower())
                elif isinstance(t, list):
                    clean_tag_list.extend([str(sub).lower() for sub in t if sub])
        tags = " ".join(clean_tag_list)
        combined = f"{title} {desc} {tags}"

        # Exclusion filter
        if any(bad in title for bad in exclude):
            continue

        # Check if any target role or domain keyword matches title or body
        # Broad keywords for Hariprasad's domain:
        domain_keywords = [
            "robotics", "embedded", "firmware", "hardware", "iot", "ros",
            "opencv", "computer vision", "stm32", "microcontroller", "automation",
            "python developer", "software engineer", "c++", "c/c++", "mechatronics"
        ]

        title_match = any(role in title for role in target_roles) or any(k in title for k in domain_keywords)
        desc_match = any(k in combined for k in ["embedded", "robotics", "ros", "stm32", "microcontroller", "firmware", "iot", "opencv"])
        
        # Keep job if title matches or description heavily focuses on his core domain
        if title_match or desc_match:
            filtered_jobs.append(job)

    print(f"[*] Kept {len(filtered_jobs)} relevant vacancies matching your domain.")
    return filtered_jobs
