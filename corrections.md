The error happens because LinkedIn (and the Google Sign-In widget it uses) detects that Chromium is being controlled by Playwright. The browser leaks automation signals: navigator.webdriver=true, the --enable-automation flag, missing plugins, etc. Your aggregator.py already has a STEALTH_SCRIPT, but apply.py doesn't use it at all.
Here is the fix. You need to do two things:
Mask the automation fingerprints (stealth script + launch args).
Use a persistent browser profile so you can log in manually once and stay authenticated across runs.
Changes to src/apply.py
Replace the top imports and the two functions below. The rest of the file stays the same.
Python
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from playwright.async_api import async_playwright

# Import the stealth script from your aggregator (or paste it here)
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
        # Use domcontentloaded + longer timeout; LinkedIn auth walls often block networkidle
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

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
        sys.exit(1)

    arg = sys.argv[1]

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
            # Persistent context keeps cookies, localStorage and login sessions on disk
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

            # Mask navigator.webdriver, plugins, chrome.runtime, etc.
            await context.add_init_script(STEALTH_SCRIPT)

            for url in urls:
                await apply_to_job(context, url, profile)

            await context.close()
        print("\nAll done!")

    asyncio.run(run())
How to use it
Delete any old ./browser_data folder if it exists from a previous failed login.
Run the script. A real Chrome window will open.
When LinkedIn (or any site) asks you to log in, log in manually with email/password (avoid "Sign in with Google" if possible — Google is extra aggressive about automation detection).
Once you are logged in and can see your LinkedIn feed, close the browser window.
From now on, every time you run apply.py, it will reuse ./browser_data and you will already be authenticated.
Why this works
| Detection signal                    | How the fix counters it                                    |
| ----------------------------------- | ---------------------------------------------------------- |
| `navigator.webdriver = true`        | `STEALTH_SCRIPT` overrides it to `undefined`               |
| `--enable-automation` flag          | `--disable-blink-features=AutomationControlled` removes it |
| Generic headless user agent         | Hardcoded real Chrome macOS user agent                     |
| Missing plugins / `chrome.runtime`  | `STEALTH_SCRIPT` fakes them                                |
| Cookies lost every run              | `launch_persistent_context` saves them to `./browser_data` |
| `networkidle` timeout on auth walls | Changed to `domcontentloaded` with 45 s timeout            |

If Google Sign-In still blocks you
Some sites force Google OAuth. If LinkedIn keeps showing the "not secure" error even after the stealth changes:
Use email/password login on LinkedIn instead of Google.
Or, log in to LinkedIn on your normal Chrome browser, export cookies with an extension like EditThisCookie, and load them via Playwright's storage_state. But the persistent-context method above is usually enough.
The screenshot crash (Target page, context or browser has been closed) is also fixed — the error handler now checks page.is_closed() before trying to screenshot.