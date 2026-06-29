import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from src.config import SearchConfig
from src.llm import evaluate_job
from src.models import JobListing, parse_relative_time
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

    from datetime import datetime, timedelta

    if config.hours_since_posted:
        cutoff = datetime.now() - timedelta(hours=config.hours_since_posted)
        recent = []
        for job in unique:
            posted = parse_relative_time(job.posted_date or "")
            if posted and posted >= cutoff:
                recent.append(job)
            elif not job.posted_date:
                recent.append(job)
        unique = recent
        print(f"Jobs posted within last {config.hours_since_posted}h: {len(unique)}")

    if config.startup_only:
        startup_kw = ["startup", "early stage", "seed", "series a", "founding", "angel"]
        filtered = []
        for job in unique:
            text = f"{job.title} {job.company} {job.description}".lower()
            if any(k in text for k in startup_kw) or job.source == "wellfound":
                filtered.append(job)
        unique = filtered
        print(f"Startup jobs: {len(unique)}")

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
