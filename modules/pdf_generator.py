import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
from config import TEMPLATES_DIR, TAILORED_DIR

def sanitize_filename(name: str) -> str:
    """Replaces characters not safe for Windows filenames."""
    return re.sub(r'[\\/*?:"<>| ]+', '_', name).strip('_')

def generate_pdf(tailored_profile: dict, company: str, title: str) -> Path:
    """
    Renders Jinja2 HTML template with the tailored candidate data and
    exports an ATS-friendly, pixel-perfect PDF using Playwright Chromium.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("resume_template.html")
    
    html_content = template.render(**tailored_profile)
    
    # Define file paths
    company_clean = sanitize_filename(company)
    title_clean = sanitize_filename(title)
    filename = f"Resume_Hariprasad_Anand_{company_clean}_{title_clean}"
    
    html_path = TAILORED_DIR / f"{filename}.html"
    pdf_path = TAILORED_DIR / f"{filename}.pdf"

    # Save rendered HTML
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Convert to PDF via Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="Letter",
            print_background=True,
            margin={"top": "0.3in", "bottom": "0.3in", "left": "0.4in", "right": "0.4in"}
        )
        browser.close()

    print(f"[+] Successfully generated tailored PDF: {pdf_path.name}")
    return pdf_path
