The root cause is bot detection + stale selectors. LinkedIn is more permissive, but Naukri, Indeed, and Wellfound aggressively block headless Chromium or use dynamic class names that changed since the code was written.
Here is exactly what to change — copy-paste replace these 4 files:
1. src/aggregator.py
Add stealth anti-detection to every browser context, and save into the subdirectories you asked for.
Python
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from src.config import SearchConfig
from src.llm import evaluate_job
from src.models import JobListing
from src.sources.greenhouse import GreenhouseSource
from src.sources.indeed import IndeedSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.naukri import NaukriSource
from src.sources.wellfound import WellfoundSource

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = { runtime: {} };
"""

async def new_stealth_context(browser):
    context = await browser.new_context(
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
    return context


async def aggregate(config: SearchConfig, profile: str) -> list[JobListing]:
    print("=" * 60)
    print("JOB AGGREGATOR")
    print(f"Keywords: {config.keywords}")
    print(f"Location: {config.location}")
    print(f"Min Salary: {config.min_salary or 'Any'}")
    print(f"Experience: {config.experience_level}")
    print(f"Exclude: {', '.join(config.exclude_keywords)}")
    print("=" * 60)

    all_jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # LinkedIn
        context = await new_stealth_context(browser)
        page = await context.new_page()
        jobs = await LinkedInSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        # Naukri
        context = await new_stealth_context(browser)
        page = await context.new_page()
        jobs = await NaukriSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        # Indeed
        context = await new_stealth_context(browser)
        page = await context.new_page()
        jobs = await IndeedSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        # Greenhouse — add your target company slugs here
        greenhouse_boards = [
            # "stripe", "airbnb", "notion", "figma"
        ]
        for board in greenhouse_boards:
            context = await new_stealth_context(browser)
            page = await context.new_page()
            jobs = await GreenhouseSource.scrape(board, page)
            all_jobs.extend(jobs)
            await context.close()

        # Lever — add your target company slugs here
        lever_slugs = [
            # "netflix", "spotify", "shopify"
        ]
        for slug in lever_slugs:
            context = await new_stealth_context(browser)
            page = await context.new_page()
            jobs = await LeverSource.scrape(slug, page)
            all_jobs.extend(jobs)
            await context.close()

        # Wellfound
        context = await new_stealth_context(browser)
        page = await context.new_page()
        jobs = await WellfoundSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        await browser.close()

    print(f"\nTotal collected: {len(all_jobs)}")

    seen = set()
    unique = []
    for j in all_jobs:
        if j.url not in seen:
            seen.add(j.url)
            unique.append(j)
    print(f"Unique after dedup: {len(unique)}")

    print("\nEvaluating jobs...")
    evaluated = []
    for i, job in enumerate(unique):
        print(f"  [{i+1}/{len(unique)}] {job.title[:50]}... ({job.source})")
        score, reason, salary = await evaluate_job(job, profile, config)
        job.relevance_score = score
        job.reason = reason
        if salary:
            job.salary = salary

        if score < 20:
            print(f"    Skipped (score {score:.0f})")
            continue
        combined = f"{job.title} {job.description}".lower()
        if any(ex.lower() in combined for ex in config.exclude_keywords):
            print("    Skipped (excluded keyword)")
            continue

        evaluated.append(job)
        print(f"    Score {score:.0f}: {reason}")

    evaluated.sort(key=lambda x: x.relevance_score, reverse=True)
    return evaluated


def save_results(jobs: list[JobListing], prefix: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    json_dir = Path("output/jobs_found")
    txt_dir = Path("output/jobs_to_apply")
    json_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    json_file = json_dir / (
        f"jobs_found_{prefix}{ts}.json" if prefix else f"jobs_found_{ts}.json"
    )
    txt_file = txt_dir / (
        f"jobs_to_apply_{prefix}{ts}.txt" if prefix else f"jobs_to_apply_{ts}.txt"
    )

    json_file.write_text(json.dumps([j.to_dict() for j in jobs], indent=2))
    txt_file.write_text("\n".join(j.url for j in jobs))

    print(f"\nSaved {len(jobs)} jobs:")
    print(f"  JSON: {json_file}")
    print(f"  URLs: {txt_file}")
2. src/sources/naukri.py
Naukri obfuscates classes and lazy-loads content. This version scrolls, waits longer, and tries multiple selector fallbacks.
Python
import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class NaukriSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        kw_slug = config.keywords.replace(" ", "-").lower()
        base = f"https://www.naukri.com/{kw_slug}-jobs"
        params: dict[str, str] = {"k": config.keywords}
        if config.naukri_experience:
            params["experience"] = config.naukri_experience
        if config.naukri_salary_lakhs:
            params["ctcFilter"] = config.naukri_salary_lakhs
        if config.remote_only:
            params["wfhType"] = "1"

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = NaukriSource.build_url(config)
        print(f"  Naukri: {url[:90]}...")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)

            # Scroll to force lazy-load render
            for _ in range(4):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Try multiple selectors because Naukri changes classes often
            listings = await page.query_selector_all(".srp-jobtuple-wrapper")
            if not listings:
                listings = await page.query_selector_all("article.jobTuple")
            if not listings:
                listings = await page.query_selector_all("div.jobTuple")
            if not listings:
                listings = await page.query_selector_all("[data-job-id]")

            print(f"    Found {len(listings)} listings")

            jobs: list[JobListing] = []
            for listing in listings[:20]:
                try:
                    title_el = await listing.query_selector(
                        "a.title, a[class*='title'], h2 a"
                    )
                    company_el = await listing.query_selector(
                        "a.comp-name, [class*='comp-name'], a[href*='/company/']"
                    )
                    loc_el = await listing.query_selector(
                        "span.locWdth, span[class*='loc'], div[class*='loc']"
                    )
                    desc_el = await listing.query_selector(
                        "span.job-desc, span[class*='desc']"
                    )
                    salary_el = await listing.query_selector(
                        "span.sal, span[class*='sal']"
                    )
                    exp_el = await listing.query_selector(
                        "span.expwdth, span[class*='exp']"
                    )

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""
                    description = await desc_el.inner_text() if desc_el else ""
                    salary = await salary_el.inner_text() if salary_el else ""
                    exp = await exp_el.inner_text() if exp_el else ""

                    if title and href:
                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.naukri.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title.strip(),
                                company=company.strip(),
                                location=(location.strip() or exp),
                                url=full_url,
                                salary=salary.strip() if salary else None,
                                description=description.strip(),
                                source="naukri",
                            )
                        )
                except Exception:
                    continue

            print(f"    {len(jobs)} Naukri jobs")
            return jobs

        except Exception as e:
            print(f"    Naukri error: {e}")
            return []
3. src/sources/indeed.py
Indeed serves a cookie-consent wall in many regions and uses several different card layouts. This handles the consent click and tries multiple card selectors.
Python
import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class IndeedSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        base = "https://www.indeed.com/jobs"
        params = {
            "q": config.keywords,
            "l": config.location,
            "fromage": "1",  # last 24 hours
        }
        if config.remote_only:
            params["sc"] = "0kf:attr(DSQF7);"

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = IndeedSource.build_url(config)
        print(f"  Indeed: {url[:90]}...")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Dismiss cookie/consent dialogs (EU / US variants)
            for btn_text in ["Accept", "Accept all", "Skip", "Continue"]:
                try:
                    btn = await page.query_selector(
                        f"button:has-text('{btn_text}'), "
                        f"button#onetrust-accept-btn-handler, "
                        f".gnav-CookieConsentButton"
                    )
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    pass

            # Scroll to load more results
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Multiple fallback selectors for job cards
            cards = await page.query_selector_all(".job_seen_beacon")
            if not cards:
                cards = await page.query_selector_all("div.slider_container")
            if not cards:
                cards = await page.query_selector_all("div[data-testid='jobTitle-click']")
            if not cards:
                cards = await page.query_selector_all("div.mosaic-provider-jobcard")

            print(f"    Found {len(cards)} cards")

            jobs: list[JobListing] = []
            for card in cards[:15]:
                try:
                    title_el = await card.query_selector(
                        "h2 a, a.jcs-JobTitle, .jobTitle a, a[id*='job_']"
                    )
                    company_el = await card.query_selector(
                        ".companyName, [data-testid='company-name'], span.company"
                    )
                    loc_el = await card.query_selector(
                        "[data-testid='job-location'], div.companyLocation, span.location"
                    )

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""

                    if title and href:
                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.indeed.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title.strip(),
                                company=company.strip(),
                                location=location.strip(),
                                url=full_url,
                                source="indeed",
                            )
                        )
                except Exception:
                    continue

            print(f"    {len(jobs)} Indeed jobs")
            return jobs

        except Exception as e:
            print(f"    Indeed error: {e}")
            return []
4. src/sources/wellfound.py
Wellfound uses Next.js with hashed class names. The most robust approach is to grab every a[href*="/jobs/"], deduplicate, and parse title/company from the link text.
Python
import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class WellfoundSource:
    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        # Wellfound expects slugified roles like "full-stack-engineer"
        roles = quote(config.keywords.replace(" ", "-").lower())
        url = f"https://wellfound.com/jobs?roles={roles}"
        if config.location and config.location.lower() != "remote":
            url += f"&location={quote(config.location)}"
        print(f"  Wellfound: {url[:90]}...")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)

            # Infinite scroll
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            jobs: list[JobListing] = []
            seen_hrefs: set[str] = set()

            # Try structured cards first
            listings = await page.query_selector_all("[data-test='job-listing']")
            if not listings:
                listings = await page.query_selector_all("[data-testid='job-listing']")

            if listings:
                for listing in listings[:20]:
                    try:
                        link_el = await listing.query_selector("a[href*='/jobs/']")
                        if not link_el:
                            continue

                        href = await link_el.get_attribute("href")
                        if not href or href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)

                        text = await link_el.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        title = lines[0] if lines else ""
                        company = lines[1] if len(lines) > 1 else ""

                        comp_el = await listing.query_selector(
                            "[data-test='company-name'], [class*='company']"
                        )
                        if comp_el:
                            company = await comp_el.inner_text()

                        full_url = (
                            href if href.startswith("http") else f"https://wellfound.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company.strip(),
                                location=config.location,
                                url=full_url,
                                source="wellfound",
                            )
                        )
                    except Exception:
                        continue
            else:
                # Fallback: grab every job link on the page
                all_links = await page.query_selector_all("a[href*='/jobs/']")
                for link in all_links:
                    try:
                        href = await link.get_attribute("href")
                        if not href or href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)

                        text = await link.inner_text()
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        if not lines:
                            continue

                        title = lines[0]
                        company = lines[1] if len(lines) > 1 else ""

                        full_url = (
                            href if href.startswith("http") else f"https://wellfound.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=config.location,
                                url=full_url,
                                source="wellfound",
                            )
                        )
                    except Exception:
                        continue

            print(f"    {len(jobs)} Wellfound jobs")
            return jobs

        except Exception as e:
            print(f"    Wellfound error: {e}")
            return []
What changed & why
Table
Platform	Problem	Fix
All	Headless browser detected as bot	Stealth init script patches navigator.webdriver, plugins, chrome.runtime
Naukri	Dynamic obfuscated classes, lazy load	Multiple fallback selectors + page scroll + 5s wait
Indeed	Cookie consent wall blocks content, card class varies	Auto-clicks consent buttons + tries 4 different card selectors
Wellfound	Hashed CSS classes, infinite scroll	Scrolls 5 times, falls back to scraping every a[href*="/jobs/"]
Output	Saved flat in output/	Now saves JSON to output/jobs_found/ and URLs to output/jobs_to_apply/
If you still get 0 results from Naukri / Indeed
Those sites use Cloudflare / DataDome that detects even stealth headless browsers. The nuclear option is to connect to your real browser (Brave/Chrome) that already has cookies and a normal fingerprint:
Step 1: Start Brave with remote debugging
bash
/Applications/Brave\ Browser.app/Contents/MacOS/Brave\ Browser \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/brave_debug
Step 2: In src/aggregator.py, replace:
Python
browser = await p.chromium.launch(headless=True)
with:
Python
browser = await p.chromium.connect_over_cdp("http://localhost:9222")
Then re-run:
bash
uv run python -m src.cli --keywords "Full Stack Engineer" --time-filter r6400
This uses your real logged-in browser, so Naukri and Indeed will treat it like a normal user.