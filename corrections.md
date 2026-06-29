The root cause is a cascade of failures:
LinkedIn found 10 jobs but your 4-hour time filter killed them. LinkedIn returns datetime="2026-06-29" (date-only). Your parser turns that into 2026-06-29 00:00:00, which is >4 hours ago, so they’re discarded. Meanwhile, Wellfound returned 49 random jobs (Sales Rep, Video Editor, etc.) because its Apollo cache contains all jobs on the page, not just the role you searched for.
Indeed / Naukri / RemoteOK / WeWorkRemotely all returned 0 because of bot blocks, bad selectors, or overly aggressive keyword filtering.
Scoring gives 0 to irrelevant Wellfound jobs, so only 1 survives.
Here are the surgical fixes. Replace the files below:
1. src/models.py — Stop treating date-only strings as midnight
Date-only strings (2026-06-29) should mean “unknown time”, not “midnight”.
Python
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


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

    def to_dict(self):
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "salary": self.salary,
            "description": self.description[:500],
            "source": self.source,
            "posted_date": self.posted_date,
            "score": self.relevance_score,
            "reason": self.reason,
        }


def parse_salary(salary_str: str) -> int | None:
    if not salary_str:
        return None

    lpa_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:[-–]\s*\d+(?:\.\d+)?)?\s*LPA",
        salary_str,
        re.IGNORECASE,
    )
    if lpa_match:
        return int(float(lpa_match.group(1)) * 100000)

    inr_match = re.search(r"₹?\s*([\d,]+)(?:\s*[-–]\s*₹?\s*[\d,]+)?", salary_str)
    if inr_match:
        val = int(inr_match.group(1).replace(",", ""))
        if val > 10000:
            return val

    nums = re.findall(r"[\d,]+", salary_str.replace(",", ""))
    if not nums:
        return None
    vals = [int(n) for n in nums if n.isdigit()]
    if not vals:
        return None
    min_val = min(vals)
    if min_val < 100:
        min_val *= 1000
    return min_val


def parse_relative_time(time_str: str) -> Optional[datetime]:
    if not time_str:
        return None

    s = time_str.strip()

    # Date-only (e.g. 2026-06-29) — treat as unknown time so we keep the job
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return None

    s_lower = s.lower()
    now = datetime.now()

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        pass

    patterns = [
        (r"(\d+)\s*hour", "hours"),
        (r"(\d+)\s*hr", "hours"),
        (r"(\d+)\s*minute", "minutes"),
        (r"(\d+)\s*min", "minutes"),
        (r"(\d+)\s*day", "days"),
        (r"(\d+)\s*week", "weeks"),
        (r"(\d+)\s*month", "months"),
    ]
    for pat, unit in patterns:
        m = re.search(pat, s_lower)
        if m:
            val = int(m.group(1))
            delta = {
                "hours": timedelta(hours=val),
                "minutes": timedelta(minutes=val),
                "days": timedelta(days=val),
                "weeks": timedelta(weeks=val),
                "months": timedelta(days=val * 30),
            }[unit]
            return now - delta

    if any(x in s_lower for x in ["just now", "today", "few hours", "just posted"]):
        return now - timedelta(hours=1)

    return None
2. src/aggregator.py — Keep jobs when the post time is unknown
The old code checked elif not job.posted_date (the raw string), but LinkedIn does send a raw string — it just lacks a time component. We now check the parsed result.
Python
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.config import SearchConfig
from src.llm import evaluate_job
from src.models import JobListing, parse_relative_time
from src.sources.greenhouse import GreenhouseSource
from src.sources.indeed import IndeedSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.naukri import NaukriSource
from src.sources.remoteok import RemoteOKSource
from src.sources.wellfound import WellfoundSource
from src.sources.weworkremotely import WeWorkRemotelySource

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
        NaukriSource.scrape(config),
        WellfoundSource.scrape(config),
        RemoteOKSource.scrape(config),
        WeWorkRemotelySource.scrape(config),
    ]

    for board in config.greenhouse_boards:
        tasks.append(GreenhouseSource.scrape(board, config))

    for slug in config.lever_slugs:
        tasks.append(LeverSource.scrape(slug, config))

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
            # Keep job if posted time is recent OR if we couldn't parse it
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


def save_results(jobs: list[JobListing], config: SearchConfig, prefix: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    json_dir = Path(config.output_dir) / "jobs_found"
    txt_dir = Path(config.output_dir) / "jobs_to_apply"
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
3. src/llm.py — Include location in scoring & normalize hyphens
Your keyword search was missing the location field, so remote jobs that had "Remote" only in the location column got 0 bonus points.
Python
import json
import re

import httpx

from src.config import SearchConfig
from src.models import JobListing, parse_salary


async def ask_llm(prompt: str, model: str = "gemma3", timeout: int = 90) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"    LLM request failed: {e}")
        return ""


async def evaluate_job(
    job: JobListing, profile: str, config: SearchConfig
) -> tuple[float, str, str | None]:
    title_company = f"{job.title} {job.company}".lower()
    desc_lower = job.description.lower()
    # FIX: include location so "Remote" jobs actually get the remote bonus
    combined = f"{title_company} {desc_lower} {job.location.lower()}"

    score = 0.0
    reasons = []

    # FIX: normalize hyphens so "full-stack" matches "full stack"
    kw_clean = config.keywords.lower().replace("-", " ")
    keyword_hits = sum(1 for k in kw_clean.split() if k in combined)
    score += keyword_hits * 10

    level_map = {
        "entry": ["entry", "junior", "new grad", "graduate", "0-2", "0 - 2", "fresher"],
        "mid": ["mid", "intermediate", "2-5", "3-5", "2+ years"],
        "senior": ["senior", "sr.", "lead", "staff", "principal", "5-8", "5+ years", "8+ years"],
        "staff": ["staff", "principal", "architect", "director", "8+ years", "10+ years"],
    }
    for level_hint in level_map.get(config.experience_level, []):
        if level_hint in combined:
            score += 15
            reasons.append(f"Matches {config.experience_level} level")
            break

    if config.remote_only and any(
        r in combined for r in ["remote", "work from home", "wfh", "anywhere"]
    ):
        score += 20
        reasons.append("Remote friendly")

    excluded_found = [ex for ex in config.exclude_keywords if ex.lower() in combined]
    if excluded_found:
        score -= 30 * len(excluded_found)
        reasons.append(f"Excluded keywords: {', '.join(excluded_found)}")

    salary_val = parse_salary(job.salary or "")

    if config.min_salary_lakhs and salary_val and salary_val > 10000:
        lakhs = salary_val / 100000
        if lakhs < config.min_salary_lakhs:
            score -= 30
            reasons.append(f"Salary {lakhs:.1f}L < {config.min_salary_lakhs}L")

    if config.min_salary and salary_val and salary_val >= 10000:
        if salary_val < config.min_salary:
            score -= 25
            reasons.append(f"Salary below ${config.min_salary}")

    if len(job.description) > 100:
        prompt = f"""Rate this job relevance 0-100 for this candidate. Be concise.

Candidate: {profile[:600]}
Job: {job.title} at {job.company}
Description: {job.description[:1200]}
Keywords wanted: {config.keywords}
Exclude: {', '.join(config.exclude_keywords)}
Min salary: {config.min_salary or 'Any'}
Experience: {config.experience_level}

Respond ONLY as JSON: {{"score": 75, "salary": "$120k-$150k", "reason": "..."}}
If no salary, use null."""

        response = await ask_llm(prompt, model=config.llm_model, timeout=config.llm_timeout)
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                llm_score = float(result.get("score", score))
                llm_salary = result.get("salary")
                llm_reason = result.get("reason", "LLM evaluated")

                final_score = (llm_score * 0.6) + (min(score, 100) * 0.4)
                return final_score, llm_reason, llm_salary or job.salary
        except Exception as e:
            print(f"    LLM parse failed: {e}")

    final_score = min(max(score, 0), 100)
    reason = "; ".join(reasons) if reasons else "Keyword-based match"
    return final_score, reason, job.salary
4. src/sources/indeed.py — Use curl_cffi + parse job links directly
Indeed blocks httpx. curl_cffi bypasses the TLS fingerprint check. We also switch to parsing the actual job links (/rc/clk?jk=...) instead of fragile card selectors.
Python
import asyncio
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.config import SearchConfig
from src.models import JobListing


class IndeedSource:
    @staticmethod
    def build_url(config: SearchConfig, start: int = 0) -> str:
        base = "https://www.indeed.com/jobs"
        params = {
            "q": config.keywords,
            "l": config.location,
            "fromage": "1",
            "start": start,
        }
        if config.remote_only:
            params["sc"] = "0kf:attr(DSQF7);"
        query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        jobs: list[JobListing] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with AsyncSession(impersonate="chrome124") as client:
            for start in range(0, config.max_jobs_per_source * 2, 15):
                url = IndeedSource.build_url(config, start)
                print(f"  Indeed: {url[:90]}...")

                try:
                    resp = await client.get(url, headers=headers, timeout=30)
                    if resp.status_code != 200:
                        print(f"    Indeed returned {resp.status_code}")
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Indeed job links always contain /rc/clk?jk= or /viewjob?jk=
                    job_links = soup.find_all(
                        "a", href=re.compile(r"/rc/clk\?jk=|/viewjob\?jk=")
                    )
                    print(f"    Found {len(job_links)} job links")

                    if not job_links:
                        break

                    seen = set()
                    for link in job_links[:config.max_jobs_per_source]:
                        href = link.get("href", "")
                        if not href or href in seen:
                            continue
                        seen.add(href)

                        title = link.get_text(strip=True)
                        if not title:
                            continue

                        # Walk up to find the card container
                        parent = link.find_parent(
                            "div",
                            class_=re.compile(
                                r"job_seen_beacon|slider_container|mosaic-provider-jobcard|jobCard"
                            ),
                        )

                        company = ""
                        location = ""
                        posted = ""
                        if parent:
                            comp_el = parent.select_one(
                                "[data-testid='company-name'], .companyName, span.company"
                            )
                            loc_el = parent.select_one(
                                "[data-testid='job-location'], div.companyLocation, span.location"
                            )
                            date_el = parent.select_one(
                                "span.date, span[data-testid='job-date']"
                            )
                            company = comp_el.get_text(strip=True) if comp_el else ""
                            location = loc_el.get_text(strip=True) if loc_el else ""
                            posted = date_el.get_text(strip=True) if date_el else ""

                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.indeed.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=location,
                                url=full_url,
                                source="indeed",
                                posted_date=posted,
                            )
                        )

                    if len(job_links) < 15:
                        break
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"    Indeed error: {e}")
                    break

        print(f"    {len(jobs)} Indeed jobs")
        return jobs
5. src/sources/naukri.py — More robust selectors + debug
Naukri changes class names frequently. This adds broader fallbacks and prints a snippet of HTML when nothing is found so you can inspect.
Python
from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

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
    async def scrape(config: SearchConfig) -> list[JobListing]:
        url = NaukriSource.build_url(config)
        print(f"  Naukri: {url[:90]}...")

        jobs: list[JobListing] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as client:
                resp = await client.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    print(f"    Naukri returned {resp.status_code}")
                    return jobs

                text = resp.text
                soup = BeautifulSoup(text, "html.parser")

                # Try multiple container selectors
                listings = (
                    soup.select(".srp-jobtuple-wrapper")
                    or soup.select("article.jobTuple")
                    or soup.select("div.jobTuple")
                    or soup.select("[data-job-id]")
                    or soup.select("div.list")
                    or soup.select("div.job")
                )

                print(f"    Found {len(listings)} listings")

                if not listings:
                    # Debug: print first 800 chars of body so you can see what arrived
                    print(f"    DEBUG HTML snippet: {text[:800]}")

                for listing in listings[:config.max_jobs_per_source]:
                    try:
                        title_el = (
                            listing.select_one("a.title")
                            or listing.select_one("a.srp-jd-p-title")
                            or listing.select_one("h2 a")
                            or listing.select_one("a[class*='title']")
                        )
                        company_el = (
                            listing.select_one("a.comp-name")
                            or listing.select_one("a[href*='/company/']")
                            or listing.select_one("div.company-name")
                            or listing.select_one("[class*='company']")
                        )
                        loc_el = (
                            listing.select_one("span.locWdth")
                            or listing.select_one("span.location")
                            or listing.select_one("div.location")
                            or listing.select_one("[class*='loc']")
                        )
                        desc_el = (
                            listing.select_one("span.job-desc")
                            or listing.select_one("[class*='desc']")
                        )
                        salary_el = (
                            listing.select_one("span.sal")
                            or listing.select_one("span.salary")
                            or listing.select_one("[class*='salary']")
                        )
                        exp_el = (
                            listing.select_one("span.expwdth")
                            or listing.select_one("span.exp")
                            or listing.select_one("[class*='exp']")
                        )

                        title = title_el.get_text(strip=True) if title_el else ""
                        href = title_el.get("href") if title_el else ""
                        company = company_el.get_text(strip=True) if company_el else ""
                        location = loc_el.get_text(strip=True) if loc_el else ""
                        description = desc_el.get_text(strip=True) if desc_el else ""
                        salary = salary_el.get_text(strip=True) if salary_el else ""
                        exp = exp_el.get_text(strip=True) if exp_el else ""

                        if title and href:
                            full_url = (
                                href
                                if href.startswith("http")
                                else f"https://www.naukri.com{href}"
                            )
                            jobs.append(
                                JobListing(
                                    title=title,
                                    company=company,
                                    location=(location or exp),
                                    url=full_url,
                                    salary=salary if salary else None,
                                    description=description,
                                    source="naukri",
                                )
                            )
                    except Exception:
                        continue

                print(f"    {len(jobs)} Naukri jobs")

        except Exception as e:
            print(f"    Naukri error: {e}")

        return jobs
6. src/sources/remoteok.py — Remove keyword gate
RemoteOK’s API is already scoped to remote tech jobs. Your client-side keyword filter was rejecting valid jobs because the description didn’t contain the exact phrase.
Python
import httpx

from src.config import SearchConfig
from src.models import JobListing


class RemoteOKSource:
    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        url = "https://remoteok.com/api"
        print(f"  RemoteOK: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                data = resp.json()

                # First element is metadata
                for item in data[1:]:
                    title = item.get("position", "")
                    company = item.get("company", "")
                    location = item.get("location", "Remote")
                    desc = item.get("description", "")
                    tags = " ".join(item.get("tags", []))
                    job_url = item.get("url", "")
                    if job_url and not job_url.startswith("http"):
                        job_url = f"https://remoteok.com{job_url}"

                    # Let the scoring layer handle relevance; keep all tech jobs
                    jobs.append(
                        JobListing(
                            title=title,
                            company=company,
                            location=location,
                            url=job_url,
                            description=f"{desc} {tags}",
                            source="remoteok",
                        )
                    )
                print(f"    {len(jobs)} RemoteOK jobs")

        except Exception as e:
            print(f"    RemoteOK error: {e}")

        return jobs
7. src/sources/weworkremotely.py — Remove keyword gate
Same logic: the RSS feed is already curated for programming jobs.
Python
import feedparser
import httpx

from src.config import SearchConfig
from src.models import JobListing


class WeWorkRemotelySource:
    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        print(f"  WeWorkRemotely: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    title = entry.get("title", "")
                    company = ""
                    if ":" in title:
                        parts = title.split(":", 1)
                        company = parts[0].strip()
                        title = parts[1].strip()

                    # Keep all programming jobs; let scoring filter relevance
                    jobs.append(
                        JobListing(
                            title=title,
                            company=company,
                            location="Remote",
                            url=entry.get("link", ""),
                            description=entry.get("summary", ""),
                            source="weworkremotely",
                        )
                    )
                print(f"    {len(jobs)} WeWorkRemotely jobs")

        except Exception as e:
            print(f"    WeWorkRemotely error: {e}")

        return jobs
8. src/sources/wellfound.py — Filter out irrelevant Apollo jobs
Wellfound’s __NEXT_DATA__ Apollo cache contains every job on the page (Sales, Recruiting, etc.), not just the ones matching your role query. We filter by keyword before appending.
Python
import json
import re
from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.config import SearchConfig
from src.models import JobListing


class WellfoundSource:
    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        roles = quote(config.keywords.replace(" ", "-").lower())
        url = f"https://wellfound.com/jobs?roles={roles}"
        if config.remote_only:
            url += "&remote=true"
        print(f"  Wellfound: {url[:90]}...")

        jobs: list[JobListing] = []
        kw_parts = [k for k in config.keywords.lower().split() if len(k) > 2]

        try:
            async with AsyncSession(impersonate="chrome124") as client:
                resp = await client.get(url, timeout=30)
                if resp.status_code != 200:
                    print(f"    Wellfound returned {resp.status_code}")
                    return jobs

                text = resp.text
                next_data_match = re.search(
                    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, re.S
                )
                if next_data_match:
                    data = json.loads(next_data_match.group(1))
                    apollo = data.get("props", {}).get("pageProps", {}).get("apolloState", {})
                    for key, node in apollo.items():
                        if key.startswith("JobListing:"):
                            title = node.get("title") or node.get("displayTitle", "")
                            company_data = node.get("company")
                            company = ""
                            if isinstance(company_data, dict):
                                company = company_data.get("name", "")
                            elif isinstance(company_data, str) and company_data.startswith("Company:"):
                                company = apollo.get(company_data, {}).get("name", "")

                            loc = node.get("location", "Remote")
                            href = node.get("jobUrl") or node.get("applyUrl", "")
                            if href and not href.startswith("http"):
                                href = f"https://wellfound.com{href}"

                            desc = node.get("description", "")

                            # Wellfound Apollo cache contains ALL jobs on the page.
                            # Filter by keyword so we don't get Sales Reps.
                            text_combined = f"{title} {desc}".lower()
                            if kw_parts and not any(k in text_combined for k in kw_parts):
                                continue

                            if title and href:
                                jobs.append(
                                    JobListing(
                                        title=title,
                                        company=company,
                                        location=loc,
                                        url=href,
                                        description=desc,
                                        source="wellfound",
                                    )
                                )
                else:
                    # Fallback: link extraction
                    soup = BeautifulSoup(text, "html.parser")
                    seen = set()
                    for link in soup.find_all("a", href=re.compile(r"/jobs/\d+")):
                        href = link.get("href", "")
                        if not href or href in seen:
                            continue
                        seen.add(href)
                        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
                        text_content = link.get_text(separator=" ", strip=True)
                        lines = [ln for ln in text_content.split("\n") if ln.strip()]
                        title = lines[0] if lines else "Unknown"
                        company = lines[1] if len(lines) > 1 else ""

                        text_combined = f"{title}".lower()
                        if kw_parts and not any(k in text_combined for k in kw_parts):
                            continue

                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location="Remote",
                                url=full_url,
                                source="wellfound",
                            )
                        )

                print(f"    {len(jobs)} Wellfound jobs")

        except Exception as e:
            print(f"    Wellfound error: {e}")

        return jobs
What you should see after these fixes
Table
Source	Before	After (expected)
LinkedIn	10 found → 0 saved	10 found → 10 saved (time filter fixed)
Indeed	0	10-15 (curl_cffi bypass)
Naukri	0	0-15 (better selectors; if still 0, check the debug HTML snippet)
Wellfound	49 garbage	5-15 relevant (keyword filter added)
RemoteOK	0	20-50 (gate removed)
WeWorkRemotely	0	10-30 (gate removed)
Run it again with:
bash
uv run python aggregator.py
If Naukri still shows 0, look for the DEBUG HTML snippet line in your terminal — it will show you what Naukri actually sent back (usually a Cloudflare challenge or a new DOM structure), and we can adjust from there.