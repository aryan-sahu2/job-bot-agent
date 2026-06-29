#!/usr/bin/env python3
"""Job Link Aggregator — searches multiple boards and filters by relevance."""

import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from playwright.async_api import async_playwright


# ─── CONFIG ──────────────────────────────────────────────────────────
@dataclass
class SearchConfig:
    keywords: list[str]              # e.g. ["python", "backend", "engineer"]
    location: str = "Remote"         # e.g. "Remote", "London", "New York"
    min_salary: Optional[int] = None  # e.g. 100000
    remote_only: bool = True
    experience_level: str = "mid"    # "entry", "mid", "senior", "staff"
    exclude_keywords: list[str] = None  # e.g. ["php", "wordpress", "salesforce"]

    def __post_init__(self):
        if self.exclude_keywords is None:
            self.exclude_keywords = []


# ─── JOB MODEL ───────────────────────────────────────────────────────
@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    salary: Optional[str] = None
    description: str = ""
    source: str = ""
    posted_date: Optional[str] = None
    relevance_score: float = 0.0
    reason: str = ""


# ─── LLM EVALUATION ──────────────────────────────────────────────────
async def evaluate_job_with_llm(job: JobListing, profile: str, config: SearchConfig) -> tuple[float, str]:
    """Use local LLM to score job relevance and extract salary."""

    prompt = f"""Rate this job's relevance for the candidate on a scale of 0-100.

Candidate Profile:
{profile[:800]}

Job Title: {job.title}
Company: {job.company}
Location: {job.location}
Description: {job.description[:1200]}

Candidate wants:
- Keywords: {', '.join(config.keywords)}
- Location preference: {config.location}
- Min salary: {config.min_salary or 'Any'}
- Experience: {config.experience_level}
- Exclude: {', '.join(config.exclude_keywords)}

Respond ONLY in this JSON format:
{{"score": 75, "salary": "$120k-$150k", "reason": "Strong match for Python backend skills, remote friendly"}}

If no salary is mentioned, use null for salary. If the job requires skills the candidate doesn't have (like {', '.join(config.exclude_keywords)}), score below 30."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": "gemma3", "prompt": prompt, "stream": False}
            )
            text = r.json().get("response", "")

            # Extract JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0))
                salary = result.get("salary")
                reason = result.get("reason", "No reason given")
                return score, salary, reason
    except Exception as e:
        print(f"  LLM eval failed: {e}")

    return 0.0, None, "Evaluation failed"


# ─── SOURCES ─────────────────────────────────────────────────────────
class LinkedInSource:
    """Search LinkedIn jobs via direct URL construction."""

    BASE_URL = "https://www.linkedin.com/jobs/search"

    @staticmethod
    def build_url(config: SearchConfig) -> str:
        params = {
            "keywords": " ".join(config.keywords),
            "location": config.location,
            "f_JT": "F" if config.remote_only else "",  # Remote filter
        }
        query = "&".join(f"{k}={v.replace(' ', '%20')}" for k, v in params.items() if v)
        return f"{LinkedInSource.BASE_URL}?{query}"

    @staticmethod
    async def scrape(page, config: SearchConfig) -> list[JobListing]:
        url = LinkedInSource.build_url(config)
        print(f"  Scraping LinkedIn: {url[:80]}...")

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)  # Let lazy-load cards appear

        jobs = []
        cards = await page.query_selector_all(".base-card")

        for card in cards[:20]:  # Limit to first 20
            try:
                title_el = await card.query_selector(".base-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle")
                loc_el = await card.query_selector(".job-search-card__location")
                link_el = await card.query_selector("a.base-card__full-link")

                title = await title_el.inner_text() if title_el else ""
                company = await company_el.inner_text() if company_el else ""
                location = await loc_el.inner_text() if loc_el else ""
                href = await link_el.get_attribute("href") if link_el else ""

                if title and href:
                    jobs.append(JobListing(
                        title=title.strip(),
                        company=company.strip(),
                        location=location.strip(),
                        url=href.split("?")[0],  # Clean tracking params
                        source="linkedin"
                    ))
            except Exception:
                continue

        print(f"  Found {len(jobs)} LinkedIn jobs")
        return jobs


class GreenhouseSource:
    """Search Greenhouse boards."""

    @staticmethod
    async def scrape(board_slug: str, page) -> list[JobListing]:
        url = f"https://boards.greenhouse.io/{board_slug}"
        print(f"  Scraping Greenhouse: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)

            jobs = []
            listings = await page.query_selector_all(".opening")

            for listing in listings:
                title_el = await listing.query_selector("a")
                if not title_el:
                    continue

                title = await title_el.inner_text()
                href = await title_el.get_attribute("href")

                # Get location from parent
                loc_el = await listing.query_selector(".location")
                location = await loc_el.inner_text() if loc_el else ""

                if title and href:
                    full_url = href if href.startswith("http") else f"https://boards.greenhouse.io{href}"
                    jobs.append(JobListing(
                        title=title.strip(),
                        company=board_slug.replace("-", " ").title(),
                        location=location.strip(),
                        url=full_url,
                        source="greenhouse"
                    ))

            print(f"  Found {len(jobs)} Greenhouse jobs for {board_slug}")
            return jobs

        except Exception as e:
            print(f"  Greenhouse error: {e}")
            return []


class LeverSource:
    """Search Lever job boards."""

    @staticmethod
    async def scrape(company_slug: str, page) -> list[JobListing]:
        url = f"https://jobs.lever.co/{company_slug}"
        print(f"  Scraping Lever: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)

            jobs = []
            listings = await page.query_selector_all(".posting")

            for listing in listings:
                title_el = await listing.query_selector("h5[data-qa='posting-title']")
                if not title_el:
                    title_el = await listing.query_selector(".posting-title")

                if not title_el:
                    continue

                title = await title_el.inner_text()
                link_el = await listing.query_selector("a")
                href = await link_el.get_attribute("href") if link_el else ""

                # Location
                loc_el = await listing.query_selector(".sort-by-time, .posting-category")
                location = await loc_el.inner_text() if loc_el else ""

                if title and href:
                    jobs.append(JobListing(
                        title=title.strip(),
                        company=company_slug.replace("-", " ").title(),
                        location=location.strip(),
                        url=href,
                        source="lever"
                    ))

            print(f"  Found {len(jobs)} Lever jobs for {company_slug}")
            return jobs

        except Exception as e:
            print(f"  Lever error: {e}")
            return []


class WellfoundSource:
    """Search Wellfound (formerly AngelList)."""

    @staticmethod
    async def scrape(page, config: SearchConfig) -> list[JobListing]:
        url = f"https://wellfound.com/jobs?roles={'+'.join(config.keywords)}&location={config.location.replace(' ', '%20')}"
        print("  Scraping Wellfound...")

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            jobs = []
            # Wellfound uses dynamic loading, try common selectors
            listings = await page.query_selector_all("[data-test='job-listing']")
            if not listings:
                listings = await page.query_selector_all(".styles_jobListing__")

            for listing in listings[:15]:
                try:
                    title_el = await listing.query_selector("[data-test='role-title']")
                    company_el = await listing.query_selector("[data-test='company-name']")
                    link_el = await listing.query_selector("a")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""

                    if title and href:
                        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
                        jobs.append(JobListing(
                            title=title.strip(),
                            company=company.strip(),
                            location=config.location,
                            url=full_url,
                            source="wellfound"
                        ))
                except:
                    continue

            print(f"  Found {len(jobs)} Wellfound jobs")
            return jobs

        except Exception as e:
            print(f"  Wellfound error: {e}")
            return []


# ─── MAIN AGGREGATOR ─────────────────────────────────────────────────
async def aggregate_jobs(config: SearchConfig, profile_text: str) -> list[JobListing]:
    print("=" * 60)
    print("JOB AGGREGATOR")
    print("=" * 60)

    all_jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Headless for scraping

        # LinkedIn
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        linkedin_jobs = await LinkedInSource.scrape(page, config)
        all_jobs.extend(linkedin_jobs)
        await context.close()

        # Greenhouse boards (add your target companies)
        greenhouse_boards = [
            # Add company slugs here, e.g.:
            # "stripe", "airbnb", "notion", "figma"
        ]
        for board in greenhouse_boards:
            context = await browser.new_context()
            page = await context.new_page()
            jobs = await GreenhouseSource.scrape(board, page)
            all_jobs.extend(jobs)
            await context.close()

        # Lever boards (add your target companies)
        lever_slugs = [
            # Add company slugs here, e.g.:
            # "netflix", "spotify", "shopify"
        ]
        for slug in lever_slugs:
            context = await browser.new_context()
            page = await context.new_page()
            jobs = await LeverSource.scrape(slug, page)
            all_jobs.extend(jobs)
            await context.close()

        # Wellfound
        context = await browser.new_context()
        page = await context.new_page()
        wellfound_jobs = await WellfoundSource.scrape(page, config)
        all_jobs.extend(wellfound_jobs)
        await context.close()

        await browser.close()

    print(f"\nTotal raw jobs collected: {len(all_jobs)}")

    # Deduplicate by URL
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        if job.url not in seen:
            seen.add(job.url)
            unique_jobs.append(job)

    print(f"Unique jobs after dedup: {len(unique_jobs)}")

    # Evaluate with LLM
    print("\nEvaluating jobs with LLM...")
    evaluated = []

    for i, job in enumerate(unique_jobs):
        print(f"  [{i+1}/{len(unique_jobs)}] {job.title[:50]}...")
        score, salary, reason = await evaluate_job_with_llm(job, profile_text, config)
        job.relevance_score = score
        job.salary = salary
        job.reason = reason

        # Filter by score and exclusions
        if score < 30:
            print(f"    ↳ Skipped (score {score}): {reason}")
            continue

        desc_lower = job.description.lower()
        if any(excl in desc_lower for excl in config.exclude_keywords):
            print("    ↳ Skipped (excluded keyword match)")
            continue

        evaluated.append(job)
        print(f"    ↳ Score {score}: {reason}")

    # Sort by score
    evaluated.sort(key=lambda x: x.relevance_score, reverse=True)

    return evaluated


def save_results(jobs: list[JobListing], filename: str = "jobs_found.json"):
    data = []
    for job in jobs:
        data.append({
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "salary": job.salary,
            "score": job.relevance_score,
            "reason": job.reason,
            "source": job.source,
        })

    Path(filename).write_text(json.dumps(data, indent=2))
    print(f"\nSaved {len(jobs)} jobs to {filename}")

    # Also save as plain URL list for apply.py
    urls = [job.url for job in jobs]
    Path("jobs_to_apply.txt").write_text("\n".join(urls))
    print("Saved URL list to jobs_to_apply.txt")


async def main():
    # Load profile
    if not Path("resume.txt").exists():
        print("Create resume.txt with your profile first!")
        sys.exit(1)

    profile = Path("resume.txt").read_text()

    # Configure search
    config = SearchConfig(
        keywords=["python", "backend", "engineer"],  # Change to your skills
        location="Remote",
        min_salary=120000,
        remote_only=True,
        experience_level="senior",
        exclude_keywords=["php", "wordpress", "salesforce", "drupal"],
    )

    jobs = await aggregate_jobs(config, profile)

    print("\n" + "=" * 60)
    print(f"TOP {min(10, len(jobs))} MATCHES")
    print("=" * 60)

    for job in jobs[:10]:
        print(f"\n{job.title}")
        print(f"  {job.company} | {job.location}")
        print(f"  Score: {job.relevance_score}/100")
        print(f"  Salary: {job.salary or 'Not listed'}")
        print(f"  Why: {job.reason}")
        print(f"  URL: {job.url}")

    save_results(jobs)

    print("\nNext steps:")
    print("  1. Review jobs_found.json")
    print("  2. Edit jobs_to_apply.txt to remove any you don't want")
    print("  3. Run: uv run python apply.py jobs_to_apply.txt")


if __name__ == "__main__":
    asyncio.run(main())
