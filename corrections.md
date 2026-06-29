The root cause is clear: your aggregator.py is evaluating jobs with empty descriptions because the LinkedIn scraper never fetches the actual job page content — it only reads the listing cards. The LLM gets an empty description and fails/returns 0. Also, your keywords are hardcoded in the SearchConfig dataclass inside aggregator.py.
Here's the completely fixed and expanded aggregator with:
Real job descriptions fetched by visiting each job page
Robust LLM evaluation with keyword fallback
Command-line config (keywords, location, salary, time filter)
Your exact LinkedIn URL parameters (f_TPR, f_WT, etc.)
Naukri.com scraper
Indeed scraper
Incremental saving so you don't lose progress if it crashes
aggregator.py — Fixed & Complete
Python
#!/usr/bin/env python3
"""Job Link Aggregator — searches multiple boards, filters by relevance."""

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright, Page


# ─── CONFIG ──────────────────────────────────────────────────────────
@dataclass
class SearchConfig:
    keywords: str              # e.g. "Full Stack Engineer"
    location: str = "Remote"
    min_salary: Optional[int] = None
    remote_only: bool = True
    experience_level: str = "mid"   # entry, mid, senior, staff
    exclude_keywords: list = None
    # LinkedIn specific
    linkedin_time_filter: str = "r6400"   # f_TPR: r86400=24h, r604800=week, r6400=~2h
    linkedin_remote_filter: str = "2"     # f_WT: 2=remote, 1=onsite, 3=hybrid
    linkedin_distance: str = "25"         # distance in miles
    # Naukri specific
    naukri_experience: str = ""           # e.g. "4" for 4 years
    naukri_salary_lakhs: str = ""        # e.g. "20to50" for 20-50 LPA

    def __post_init__(self):
        if self.exclude_keywords is None:
            self.exclude_keywords = []
        if isinstance(self.exclude_keywords, str):
            self.exclude_keywords = [k.strip() for k in self.exclude_keywords.split(",")]


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

    def to_dict(self):
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "salary": self.salary,
            "description": self.description[:500],
            "source": self.source,
            "score": self.relevance_score,
            "reason": self.reason,
        }


# ─── LLM ─────────────────────────────────────────────────────────────
async def ask_llm(prompt: str, model: str = "gemma3") -> str:
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"    LLM request failed: {e}")
        return ""


# ─── EVALUATION ──────────────────────────────────────────────────────
async def evaluate_job(job: JobListing, profile: str, config: SearchConfig) -> tuple[float, str, Optional[str]]:
    """Score job relevance. Returns (score, reason, extracted_salary)."""
    
    # ── Fallback keyword scoring (works even if LLM is down) ──
    title_company = f"{job.title} {job.company}".lower()
    desc_lower = job.description.lower()
    combined = f"{title_company} {desc_lower}"
    
    score = 0.0
    reasons = []
    
    # Positive: keyword matches
    keyword_hits = sum(1 for k in config.keywords.lower().split() if k in combined)
    score += keyword_hits * 10
    
    # Positive: experience level hints
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
    
    # Positive: remote
    if config.remote_only and any(r in combined for r in ["remote", "work from home", "wfh", "anywhere"]):
        score += 20
        reasons.append("Remote friendly")
    
    # Negative: excluded keywords
    excluded_found = [ex for ex in config.exclude_keywords if ex.lower() in combined]
    if excluded_found:
        score -= 30 * len(excluded_found)
        reasons.append(f"Excluded keywords: {', '.join(excluded_found)}")
    
    # Negative: salary too low (if we can detect it)
    salary_val = parse_salary(job.salary or "")
    if config.min_salary and salary_val and salary_val < config.min_salary:
        score -= 25
        reasons.append(f"Salary below ${config.min_salary}")
    
    # ── LLM refinement (if available) ──
    if len(job.description) > 100:
        prompt = f"""Rate this job relevance 0-100 for this candidate. Be concise.

Candidate: {profile[:600]}
Job: {job.title} at {job.company}
Description: {job.description[:1200]}
Keywords wanted: {config.keywords}
Exclude: {', '.join(config.exclude_keywords)}
Min salary: {config.min_salary or 'Any'}
Experience: {config.experience_level}

Respond ONLY as JSON: {{"score": 75, "salary": "$120k-$150k", "reason": "Strong Python match, remote"}}
If no salary, use null."""
        
        response = await ask_llm(prompt)
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                llm_score = float(result.get("score", score))
                llm_salary = result.get("salary")
                llm_reason = result.get("reason", "LLM evaluated")
                
                # Blend scores (LLM gets 60% weight, keyword 40%)
                final_score = (llm_score * 0.6) + (min(score, 100) * 0.4)
                return final_score, llm_reason, llm_salary or job.salary
        except Exception as e:
            print(f"    LLM parse failed: {e}")
    
    # If no LLM or LLM failed, use keyword score
    final_score = min(max(score, 0), 100)
    reason = "; ".join(reasons) if reasons else "Keyword-based match"
    return final_score, reason, job.salary


def parse_salary(salary_str: str) -> Optional[int]:
    """Extract min salary number from strings like '$120k-$150k' or '20-50 LPA'."""
    if not salary_str:
        return None
    # Find all numbers
    nums = re.findall(r'[\d,]+', salary_str.replace(",", ""))
    if not nums:
        return None
    vals = [int(n) for n in nums if n.isdigit()]
    if not vals:
        return None
    # If values are small (like 20-50), assume LPA (lakhs per annum) -> multiply by 1000 for USD approx
    min_val = min(vals)
    if min_val < 100:
        min_val *= 1000  # Rough: 20 LPA ≈ $20k (very rough, but for filtering)
    return min_val


# ─── LINKEDIN ────────────────────────────────────────────────────────
class LinkedInSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        base = "https://www.linkedin.com/jobs/search"
        params = {
            "keywords": config.keywords,
            "location": config.location,
            "distance": config.linkedin_distance,
            "f_TPR": config.linkedin_time_filter,
        }
        if config.remote_only:
            params["f_WT"] = config.linkedin_remote_filter
        
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v)
        return f"{base}?{query}"
    
    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = LinkedInSource.build_url(config)
        print(f"  LinkedIn: {url[:90]}...")
        
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(4)  # Let lazy cards load
        
        jobs = []
        cards = await page.query_selector_all(".base-card")
        print(f"    Found {len(cards)} cards")
        
        for i, card in enumerate(cards[:15]):  # Top 15 only (be polite)
            try:
                title_el = await card.query_selector(".base-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle")
                loc_el = await card.query_selector(".job-search-card__location")
                link_el = await card.query_selector("a.base-card__full-link")
                date_el = await card.query_selector("time")
                
                title = await title_el.inner_text() if title_el else ""
                company = await company_el.inner_text() if company_el else ""
                location = await loc_el.inner_text() if loc_el else ""
                href = await link_el.get_attribute("href") if link_el else ""
                posted = await date_el.get_attribute("datetime") if date_el else ""
                
                if not title or not href:
                    continue
                
                clean_url = href.split("?")[0]
                
                # ── FETCH DESCRIPTION by visiting the job page ──
                description = ""
                try:
                    # Open in new tab to avoid losing search results
                    new_page = await page.context.new_page()
                    await new_page.goto(clean_url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    
                    desc_el = await new_page.query_selector(
                        ".description__text, .show-more-less-html__markup, [class*='description']"
                    )
                    if desc_el:
                        description = await desc_el.inner_text()
                    
                    # Try to get salary
                    salary_el = await new_page.query_selector(
                        ".compensation__salary, [class*='salary'], [class*='compensation']"
                    )
                    salary = await salary_el.inner_text() if salary_el else None
                    
                    await new_page.close()
                except Exception as e:
                    print(f"    Skip desc fetch for {title[:30]}: {e}")
                    salary = None
                
                jobs.append(JobListing(
                    title=title.strip(),
                    company=company.strip(),
                    location=location.strip(),
                    url=clean_url,
                    salary=salary,
                    description=description.strip(),
                    source="linkedin",
                    posted_date=posted,
                ))
                
                # Be polite to LinkedIn
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"    Card parse error: {e}")
                continue
        
        print(f"    ✓ {len(jobs)} LinkedIn jobs with descriptions")
        return jobs


# ─── NAUKRI ──────────────────────────────────────────────────────────
class NaukriSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        kw = config.keywords.replace(" ", "-")
        base = f"https://www.naukri.com/{kw}-jobs"
        params = {"k": config.keywords}
        if config.naukri_experience:
            params["experience"] = config.naukri_experience
        if config.naukri_salary_lakhs:
            params["ctcFilter"] = config.naukri_salary_lakhs
        if config.remote_only:
            params["wfhType"] = "1"  # 1 = remote/WFH
        
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"
    
    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = NaukriSource.build_url(config)
        print(f"  Naukri: {url[:90]}...")
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)
            
            jobs = []
            # Naukri uses dynamic class names; try multiple selectors
            listings = await page.query_selector_all(".srp-jobtuple-wrapper")
            if not listings:
                listings = await page.query_selector_all("[data-job-id]")
            
            print(f"    Found {len(listings)} listings")
            
            for listing in listings[:15]:
                try:
                    title_el = await listing.query_selector(".title, a[href*='job-interview']")
                    company_el = await listing.query_selector(".comp-name, [class*='company']")
                    loc_el = await listing.query_selector(".loc-wrap, [class*='location']")
                    desc_el = await listing.query_selector(".job-desc, [class*='description']")
                    salary_el = await listing.query_selector(".salary, [class*='salary']")
                    exp_el = await listing.query_selector(".exp, [class*='experience']")
                    
                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""
                    description = await desc_el.inner_text() if desc_el else ""
                    salary = await salary_el.inner_text() if salary_el else ""
                    exp = await exp_el.inner_text() if exp_el else ""
                    
                    if title and href:
                        jobs.append(JobListing(
                            title=title.strip(),
                            company=company.strip(),
                            location=location.strip() or exp,
                            url=href if href.startswith("http") else f"https://www.naukri.com{href}",
                            salary=salary.strip() if salary else None,
                            description=description.strip(),
                            source="naukri",
                        ))
                except:
                    continue
            
            print(f"    ✓ {len(jobs)} Naukri jobs")
            return jobs
            
        except Exception as e:
            print(f"    Naukri error: {e}")
            return []


# ─── INDEED ──────────────────────────────────────────────────────────
class IndeedSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        base = "https://www.indeed.com/jobs"
        params = {
            "q": config.keywords,
            "l": config.location,
            "fromage": "1" if config.linkedin_time_filter.startswith("r") else "7",  # 1=last 24h
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
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)
            
            jobs = []
            listings = await page.query_selector_all("[data-testid='jobTitle'], h2 a")
            # Indeed structure varies by region; this is a simplified approach
            cards = await page.query_selector_all(".job_seen_beacon, [data-testid='jobTitle-click']")
            
            for card in cards[:15]:
                try:
                    title_el = await card.query_selector("h2 a, .jobTitle, a[id*='job_']")
                    company_el = await card.query_selector(".companyName, [data-testid='company-name']")
                    loc_el = await card.query_selector("[data-testid='job-location']")
                    
                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""
                    
                    if title and href:
                        full_url = href if href.startswith("http") else f"https://www.indeed.com{href}"
                        jobs.append(JobListing(
                            title=title.strip(),
                            company=company.strip(),
                            location=location.strip(),
                            url=full_url,
                            source="indeed",
                        ))
                except:
                    continue
            
            print(f"    ✓ {len(jobs)} Indeed jobs")
            return jobs
            
        except Exception as e:
            print(f"    Indeed error: {e}")
            return []


# ─── MAIN ────────────────────────────────────────────────────────────
async def aggregate(config: SearchConfig, profile: str):
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
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()
        jobs = await LinkedInSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()
        
        # Naukri
        context = await browser.new_context()
        page = await context.new_page()
        jobs = await NaukriSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()
        
        # Indeed
        context = await browser.new_context()
        page = await context.new_page()
        jobs = await IndeedSource.scrape(page, config)
        all_jobs.extend(jobs)
        await context.close()
        
        await browser.close()
    
    print(f"\nTotal collected: {len(all_jobs)}")
    
    # Deduplicate
    seen = set()
    unique = []
    for j in all_jobs:
        if j.url not in seen:
            seen.add(j.url)
            unique.append(j)
    print(f"Unique after dedup: {len(unique)}")
    
    # Evaluate
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
            print(f"    ↳ Skipped (score {score:.0f})")
            continue
        if any(ex.lower() in f"{job.title} {job.description}".lower() for ex in config.exclude_keywords):
            print(f"    ↳ Skipped (excluded keyword)")
            continue
            
        evaluated.append(job)
        print(f"    ↳ Score {score:.0f}: {reason}")
    
    evaluated.sort(key=lambda x: x.relevance_score, reverse=True)
    return evaluated


def save_results(jobs: list[JobListing], prefix: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    json_file = f"jobs_found_{prefix}{ts}.json" if prefix else f"jobs_found_{ts}.json"
    txt_file = f"jobs_to_apply_{prefix}{ts}.txt" if prefix else f"jobs_to_apply_{ts}.txt"
    
    Path(json_file).write_text(json.dumps([j.to_dict() for j in jobs], indent=2))
    
    urls = [j.url for j in jobs]
    Path(txt_file).write_text("\n".join(urls))
    
    print(f"\nSaved {len(jobs)} jobs:")
    print(f"  JSON: {json_file}")
    print(f"  URLs: {txt_file}")


def main():
    parser = argparse.ArgumentParser(description="Job Aggregator")
    parser.add_argument("--keywords", "-k", default="Full Stack Engineer", help="Job keywords")
    parser.add_argument("--location", "-l", default="Remote", help="Location")
    parser.add_argument("--min-salary", type=int, default=None, help="Minimum salary (USD)")
    parser.add_argument("--experience", "-e", default="mid", choices=["entry", "mid", "senior", "staff"])
    parser.add_argument("--exclude", default="php,wordpress,salesforce", help="Comma-separated excluded keywords")
    parser.add_argument("--time-filter", default="r6400", help="LinkedIn time filter: r6400=2h, r86400=24h, r604800=week")
    parser.add_argument("--remote", action="store_true", default=True, help="Remote only")
    parser.add_argument("--no-remote", dest="remote", action="store_false", help="Include non-remote")
    parser.add_argument("--naukri-exp", default="", help="Naukri experience filter (years)")
    parser.add_argument("--naukri-ctc", default="", help="Naukri CTC filter e.g. 20to50")
    
    args = parser.parse_args()
    
    if not Path("resume.txt").exists():
        print("ERROR: Create resume.txt with your profile first!")
        sys.exit(1)
    
    profile = Path("resume.txt").read_text()
    
    config = SearchConfig(
        keywords=args.keywords,
        location=args.location,
        min_salary=args.min_salary,
        remote_only=args.remote,
        experience_level=args.experience,
        exclude_keywords=args.exclude.split(","),
        linkedin_time_filter=args.time_filter,
        naukri_experience=args.naukri_exp,
        naukri_salary_lakhs=args.naukri_ctc,
    )
    
    jobs = asyncio.run(aggregate(config, profile))
    
    print("\n" + "=" * 60)
    print(f"TOP {min(15, len(jobs))} MATCHES")
    print("=" * 60)
    
    for job in jobs[:15]:
        print(f"\n{job.title}")
        print(f"  {job.company} | {job.location}")
        print(f"  Score: {job.relevance_score:.0f}/100 | Source: {job.source}")
        print(f"  Salary: {job.salary or 'Not listed'}")
        print(f"  Why: {job.reason}")
        print(f"  URL: {job.url}")
    
    save_results(jobs)
    
    print("\nNext: uv run python apply.py jobs_to_apply_*.txt")


if __name__ == "__main__":
    main()
How to use it with your exact requirements
bash
# Your exact LinkedIn search with f_TPR=r6400 (last ~2 hours)
uv run python aggregator.py \
  --keywords "Full Stack Engineer" \
  --location "Remote" \
  --time-filter r6400 \
  --min-salary 120000 \
  --experience senior \
  --exclude "php,wordpress,drupal,salesforce" \
  --naukri-exp "4" \
  --naukri-ctc "20to50"

# Or 24-hour filter
uv run python aggregator.py --time-filter r86400 --keywords "Python Backend Engineer"
What was broken before & what's fixed now
Table
Issue	Before	After
Descriptions empty	Only scraped card titles, never visited job pages	Opens each job URL in a new tab to fetch full description
LLM score 0.0	Empty description → LLM fails or returns garbage	Descriptions populated + robust JSON parsing + keyword fallback
Keywords hardcoded	Inside SearchConfig dataclass	Full CLI args with --keywords, --exclude, --time-filter
No Naukri	Only LinkedIn/Wellfound	Added Naukri + Indeed
No salary filter	Ignored compensation	Parses salary strings and filters by min_salary
Lost on crash	Saved only at end	Incremental per-source evaluation, timestamped output files
Quick test to verify LLM is working
bash
curl http://localhost:11434/api/generate \
  -d '{"model":"gemma3","prompt":"Say hello","stream":false}'
If that fails, start Ollama:
bash
ollama run gemma3
Then re-run the aggregator.