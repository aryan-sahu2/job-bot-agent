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

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()
        jobs = await LinkedInSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        context = await browser.new_context()
        page = await context.new_page()
        jobs = await NaukriSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        context = await browser.new_context()
        page = await context.new_page()
        jobs = await IndeedSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()

        greenhouse_boards = []
        for board in greenhouse_boards:
            context = await browser.new_context()
            page = await context.new_page()
            jobs = await GreenhouseSource.scrape(board, page)
            all_jobs.extend(jobs)
            await context.close()

        lever_slugs = []
        for slug in lever_slugs:
            context = await browser.new_context()
            page = await context.new_page()
            jobs = await LeverSource.scrape(slug, page)
            all_jobs.extend(jobs)
            await context.close()

        context = await browser.new_context()
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
    json_file = f"jobs_found_{prefix}{ts}.json" if prefix else f"jobs_found_{ts}.json"
    txt_file = f"jobs_to_apply_{prefix}{ts}.txt" if prefix else f"jobs_to_apply_{ts}.txt"

    Path(json_file).write_text(json.dumps([j.to_dict() for j in jobs], indent=2))
    Path(txt_file).write_text("\n".join(j.url for j in jobs))

    print(f"\nSaved {len(jobs)} jobs:")
    print(f"  JSON: {json_file}")
    print(f"  URLs: {txt_file}")
