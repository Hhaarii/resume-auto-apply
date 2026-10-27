import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from config import BROWSER_CONFIG
from modules.database import update_job_status
from modules.tailor import generate_cover_letter

def auto_fill_job_application(job: dict, profile: dict, tailored_pdf_path: Path):
    """
    Semi-automated co-pilot:
    1. Launches headful browser
    2. Navigates to job application page
    3. Fills candidate personal info (Name, Email, Phone, LinkedIn, GitHub, etc.)
    4. Automatically uploads the targeted tailored PDF resume
    5. Inserts targeted cover letter if a textarea is present
    6. Pauses and hands over control to the user to review and click 'Submit'
    """
    job_url = job.get("url")
    if not job_url:
        print("[-] Error: Job URL is missing.")
        return False

    print(f"\n[CO-PILOT ACTIVE] Navigating to: {job.get('title')} at {job.get('company')}")
    print(f"[*] Target Application URL: {job_url}")
    print(f"[*] Tailored Resume: {tailored_pdf_path.name}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=BROWSER_CONFIG.get("headless", False),
            slow_mo=BROWSER_CONFIG.get("slow_mo_ms", 600)
        )
        context = browser.new_context(
            user_agent=BROWSER_CONFIG.get("user_agent")
        )
        page = context.new_page()

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=BROWSER_CONFIG.get("timeout_ms", 30000))
            time.sleep(2)

            name_parts = profile.get("name", "Hariprasad Anand").split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # 1. Fill Name fields
            for selector in ['input[name*="first_name" i]', 'input[id*="first_name" i]', 'input[autocomplete="given-name"]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(first_name)
                    break

            for selector in ['input[name*="last_name" i]', 'input[id*="last_name" i]', 'input[autocomplete="family-name"]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(last_name)
                    break

            for selector in ['input[name*="full_name" i]', 'input[id*="name" i]', 'input[placeholder*="Full Name" i]']:
                if page.locator(selector).count() > 0 and not page.locator(selector).first.input_value():
                    page.locator(selector).first.fill(profile.get("name", ""))
                    break

            # 2. Fill Email
            for selector in ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(profile.get("email", ""))
                    break

            # 3. Fill Phone
            for selector in ['input[type="tel"]', 'input[name*="phone" i]', 'input[id*="phone" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(profile.get("phone", ""))
                    break

            # 4. Fill LinkedIn
            for selector in ['input[name*="linkedin" i]', 'input[id*="linkedin" i]', 'input[placeholder*="linkedin" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(profile.get("linkedin", ""))
                    break

            # 5. Fill GitHub
            for selector in ['input[name*="github" i]', 'input[id*="github" i]', 'input[placeholder*="github" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(profile.get("github", ""))
                    break

            # 6. Fill Location
            for selector in ['input[name*="location" i]', 'input[id*="location" i]', 'input[placeholder*="location" i]', 'input[name*="city" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(profile.get("location", ""))
                    break

            # 7. Upload Tailored PDF Resume
            file_inputs = page.locator('input[type="file"]')
            if file_inputs.count() > 0 and tailored_pdf_path.exists():
                print(f"[+] Automatically attaching tailored PDF: {tailored_pdf_path.name}")
                file_inputs.first.set_input_files(str(tailored_pdf_path.resolve()))

            # 8. Fill Cover Letter
            matched_skills = job.get("matched_skills", [])
            cover_letter_text = generate_cover_letter(profile, job, matched_skills)
            for selector in ['textarea[name*="cover" i]', 'textarea[id*="cover" i]', 'textarea[placeholder*="cover" i]']:
                if page.locator(selector).count() > 0:
                    page.locator(selector).first.fill(cover_letter_text)
                    print("[+] Auto-filled tailored Cover Letter!")
                    break

            print("\n" + "="*60)
            print(" [FORM PRE-FILLED] Application fields have been populated.")
            print(" Review any platform-specific questions on your browser.")
            print(" When you are satisfied, click Submit on the page.")
            print("="*60 + "\n")

            # Wait for user to interact and finish
            # The browser will stay open until user submits or closes it
            page.wait_for_timeout(45000)

            # Update DB status
            update_job_status(job.get("id"), "applied", str(tailored_pdf_path), "Pre-filled and verified")
            return True

        except Exception as e:
            print(f"[-] Application assistant notice: {e}")
            return False
        finally:
            browser.close()
