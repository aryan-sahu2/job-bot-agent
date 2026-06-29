import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.config import SearchConfig
from src.llm import evaluate_job
from src.models import JobListing, parse_relative_time
from src.sources.breezy import BreezySource
from src.sources.greenhouse import GreenhouseSource
from src.sources.indeed import IndeedSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.recruitee import RecruiteeSource
from src.sources.smartrecruiters import SmartRecruitersSource
from src.sources.wellfound import WellfoundSource
from src.sources.workable import WorkableSource

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = { runtime: {} };
"""


async def aggregate(config: SearchConfig, profile: str) -> list[JobListing]:
    print("=" * 60)
    print("JOB AGGREGATOR")
    print(f"Keywords: {config.keywords}")
    print(f"Location: {config.location}")
    print(f"Min Salary: {config.min_salary or 'Any'}")
    print(f"Experience: {config.experience_level}")
    print(f"Exclude: {', '.join(config.exclude_keywords)}")
    print("=" * 60)

    tasks = [
        LinkedInSource.scrape(config),
        IndeedSource.scrape(config),
        WellfoundSource.scrape(config),
    ]

    for board in config.greenhouse_boards:
        tasks.append(GreenhouseSource.scrape(board, config))

    for slug in config.lever_slugs:
        tasks.append(LeverSource.scrape(slug, config))

    for slug in config.breezy_boards:
        tasks.append(BreezySource.scrape(slug, config))

    for slug in config.recruitee_boards:
        tasks.append(RecruiteeSource.scrape(slug, config))

    for account in config.workable_accounts:
        tasks.append(WorkableSource.scrape(account, config))

    for company in config.smartrecruiters_companies:
        tasks.append(SmartRecruitersSource.scrape(company, config))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_jobs: list[JobListing] = []
    for result in results:
        if isinstance(result, list):
            all_jobs.extend(result)
        elif isinstance(result, Exception):
            print(f"Source error: {result}")

    print(f"\nTotal collected: {len(all_jobs)}")

    seen = set()
    unique = []
    for j in all_jobs:
        if j.url not in seen:
            seen.add(j.url)
            unique.append(j)
    print(f"Unique after dedup: {len(unique)}")

    if config.hours_since_posted:
        cutoff = datetime.now() - timedelta(hours=config.hours_since_posted)
        recent = []
        for job in unique:
            posted = parse_relative_time(job.posted_date or "")
            if posted is None or posted >= cutoff:
                recent.append(job)
        unique = recent
        print(f"Jobs posted within last {config.hours_since_posted}h (or unknown): {len(unique)}")

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
        print(f"  [{i + 1}/{len(unique)}] {job.title[:50]}... ({job.source})")
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


def save_results(jobs: list[JobListing], config: SearchConfig, prefix: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    json_dir = Path(config.output_dir) / "jobs_found"
    txt_dir = Path(config.output_dir) / "jobs_to_apply"
    json_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    json_file = json_dir / (f"jobs_found_{prefix}{ts}.json" if prefix else f"jobs_found_{ts}.json")
    txt_file = txt_dir / (
        f"jobs_to_apply_{prefix}{ts}.txt" if prefix else f"jobs_to_apply_{ts}.txt"
    )

    json_file.write_text(json.dumps([j.to_dict() for j in jobs], indent=2))
    txt_file.write_text("\n".join(j.url for j in jobs))

    print(f"\nSaved {len(jobs)} jobs:")
    print(f"  JSON: {json_file}")
    print(f"  URLs: {txt_file}")
    print("\nNext steps:")
    print("  1. uv run python src/server.py")
    print("  2. Install jobbot-assistant.user.js in Tampermonkey")
    print("  3. Open job URLs from output/jobs_to_apply/*.txt")
