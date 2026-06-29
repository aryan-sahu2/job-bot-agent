import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.async_api import async_playwright

from src.aggregator import STEALTH_SCRIPT

RESUME_PATH = "resume.txt"
LLM_API = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3"


def load_profile():
    text = Path(RESUME_PATH).read_text()
    lines = text.strip().split("\n")
    name = lines[0] if lines else "Applicant"
    email = next((line for line in lines if "@" in line), "")
    phone = next((line for line in lines if any(c.isdigit() for c in line) and len(line) > 9), "")
    return {"name": name, "email": email, "phone": phone, "raw": text}


async def ask_llm(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(LLM_API, json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
        })
        return r.json().get("response", "").strip()


async def parse_job(page):
    title = await page.evaluate("() => document.querySelector('h1')?.innerText || ''")
    company = await page.evaluate("""
        () => {
            const el = document.querySelector(
                '[class*="company"], [class*="employer"], meta[property="og:site_name"]'
            );
            return el?.content || el?.innerText || '';
        }
    """)
    description = await page.evaluate("""
        () => {
            const el = document.querySelector(
                '[class*="description"], [class*="job-description"], #jobDescriptionText'
            );
            return el?.innerText?.substring(0, 3000) || document.body.innerText.substring(0, 3000);
        }
    """)
    return {
        "title": title.strip(),
        "company": company.strip(),
        "description": description.strip(),
    }


async def generate_answers(job, profile):
    prompt = f"""You are {profile['name']}. Write a brief, professional cover letter for this job:

Company: {job['company']}
Role: {job['title']}
Description: {job['description'][:1500]}

Your profile:
{profile['raw'][:1000]}

Write 2-3 short paragraphs. Be specific, not generic. Mention relevant skills and experience."""

    cover_letter = await ask_llm(prompt)

    return {
        "first_name": profile["name"].split()[0],
        "last_name": profile["name"].split()[-1] if len(profile["name"].split()) > 1 else "",
        "email": profile["email"],
        "phone": profile["phone"],
        "cover_letter": cover_letter,
        "resume": "resume.pdf",
    }


async def fill_form(page, answers):
    fields = await page.query_selector_all(
        "input:not([type='hidden']):not([type='submit']), textarea, select"
    )

    filled = 0
    for field in fields:
        try:
            tag = await field.evaluate("el => el.tagName.toLowerCase()")
            input_type = await field.evaluate("el => el.type?.toLowerCase() || 'text'")
            name = await field.evaluate("el => el.name || ''")
            id_val = await field.evaluate("el => el.id || ''")
            placeholder = await field.evaluate("el => el.placeholder || ''")

            label = await field.evaluate("""
                el => {
                    const forLabel = document.querySelector(`label[for="${el.id}"]`);
                    if (forLabel) return forLabel.innerText;
                    const parentLabel = el.closest('label');
                    if (parentLabel) return parentLabel.innerText;
                    return el.getAttribute('aria-label') || '';
                }
            """)

            combined = f"{label} {placeholder} {name} {id_val}".lower()
            value = None

            if any(k in combined for k in ["first name", "given name", "fname"]):
                value = answers.get("first_name", "")
            elif any(k in combined for k in ["last name", "surname", "lname"]):
                value = answers.get("last_name", "")
            elif "email" in combined:
                value = answers.get("email", "")
            elif any(k in combined for k in ["phone", "mobile", "cell"]):
                value = answers.get("phone", "")
            elif any(k in combined for k in ["cover letter", "additional", "message"]):
                value = answers.get("cover_letter", "")
            elif any(k in combined for k in ["resume", "cv", "upload"]):
                if input_type == "file":
                    resume_path = answers.get("resume")
                    if resume_path and Path(resume_path).exists():
                        await field.set_input_files(resume_path)
                        filled += 1
                continue
            elif tag == "select":
                options = await field.query_selector_all("option")
                for opt in options:
                    opt_text = await opt.inner_text()
                    if any(k in opt_text.lower() for k in ["yes", "confirm", "agree", "submit"]):
                        await field.select_option(label=opt_text.strip())
                        filled += 1
                        break
                continue

            if value:
                await field.fill(value)
                filled += 1

        except Exception as e:
            print(f"  Skip field: {e}")
            continue

    print(f"Filled {filled} fields")
    return filled


async def apply_to_job(context, url, profile):
    print(f"\n{'='*60}")
    print(f"Applying to: {url}")
    print(f"{'='*60}")

    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        try:
            body_text = await page.inner_text("body", timeout=5000)
            login_blocks = [
                "Couldn't sign you in",
                "This browser or app may not be secure",
                "Sign in to LinkedIn",
                "Join now",
                "Be great at what you do",
            ]
            if any(block in body_text for block in login_blocks):
                print("  LinkedIn login required — skipping. Apply manually.")
                return
        except Exception:
            pass

        job = await parse_job(page)
        print(f"Job: {job['title']} at {job['company']}")

        print("Generating answers...")
        answers = await generate_answers(job, profile)

        apply_selectors = [
            "button:has-text('Apply')",
            "button:has-text('Apply Now')",
            "a:has-text('Apply')",
            "[data-testid*='apply']",
            "input[type='submit'][value*='Apply']",
        ]

        apply_clicked = False
        for sel in apply_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    apply_clicked = True
                    print("Clicked Apply button")
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue

        if not apply_clicked:
            print("No apply button found — may already be on application form")

        print("Filling form...")
        await fill_form(page, answers)

        screenshot_path = f"screenshots/{uuid4().hex[:8]}.png"
        Path("screenshots").mkdir(exist_ok=True)
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved: {screenshot_path}")

        print("\n" + "="*60)
        print("FORM FILLED — REVIEW BEFORE SUBMITTING")
        print("="*60)
        input("Press Enter AFTER you review and submit (or Ctrl+C to skip)... ")

        print("Done with this job.\n")

    except Exception as e:
        print(f"ERROR: {e}")
        try:
            if not page.is_closed():
                err_path = f"screenshots/error_{uuid4().hex[:8]}.png"
                Path("screenshots").mkdir(exist_ok=True)
                await page.screenshot(path=err_path, full_page=True)
                print(f"Error screenshot saved: {err_path}")
        except Exception as screenshot_err:
            print(f"Could not take error screenshot: {screenshot_err}")
    finally:
        if not page.is_closed():
            await page.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python apply.py <job_url_file_or_url>")
        print("\nExample:")
        print('  uv run python apply.py "https://boards.greenhouse.io/company/jobs/123"')
        print("\nOr create a file with one URL per line:")
        print("  uv run python apply.py jobs.txt")
        print("\nCDP mode (connect to real Chrome):")
        print("  uv run python apply.py --cdp output/jobs_to_apply_*.txt")
        sys.exit(1)

    args_list = sys.argv[1:]
    use_cdp = "--cdp" in args_list
    args_list = [a for a in args_list if a != "--cdp"]

    if not args_list:
        print("ERROR: No URL file provided")
        sys.exit(1)

    arg = args_list[0]

    path = Path(arg)
    if not path.exists():
        path = Path("output") / arg
    if path.exists():
        urls = [line.strip() for line in path.read_text().split("\n") if line.strip()]
    else:
        urls = [arg]

    profile = load_profile()
    print(f"Loaded profile for: {profile['name']}")

    async def run():
        async with async_playwright() as p:
            if use_cdp:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
            else:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir="./browser_data",
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1440, "height": 900},
                    locale="en-US",
                    timezone_id="America/New_York",
                )

            await context.add_init_script(STEALTH_SCRIPT)

            for url in urls:
                await apply_to_job(context, url, profile)

            if use_cdp:
                await browser.close()
            else:
                await context.close()
        print("\nAll done!")

    asyncio.run(run())
