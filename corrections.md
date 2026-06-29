Create one config.json at the project root. The script will read it on every run. CLI flags become overrides — if you don’t pass a flag, the value from config.json is used.
Here is the complete setup.
1. Create config.json in your project root
JSON
{
  "keywords": "Full Stack Engineer",
  "location": "Remote",
  "min_salary": null,
  "min_salary_lakhs": 15.0,
  "remote_only": true,
  "experience_level": "mid",
  "exclude_keywords": [
    "php",
    "wordpress",
    "salesforce",
    "drupal"
  ],
  "hours_since_posted": 4,
  "startup_only": false,
  "linkedin_time_filter": "r86400",
  "linkedin_remote_filter": "2",
  "linkedin_distance": "25",
  "naukri_experience": "",
  "naukri_salary_lakhs": "",
  "greenhouse_boards": [],
  "lever_slugs": [],
  "max_jobs_per_source": 15,
  "llm_api": "http://localhost:11434/api/generate",
  "llm_model": "gemma3",
  "llm_timeout": 90,
  "output_dir": "output",
  "resume_path": "resume.txt"
}
2. Replace src/config.py entirely
Python
from dataclasses import dataclass, field
import json
from pathlib import Path


DEFAULT_CONFIG = {
    "keywords": "Full Stack Engineer",
    "location": "Remote",
    "min_salary": None,
    "min_salary_lakhs": 15.0,
    "remote_only": True,
    "experience_level": "mid",
    "exclude_keywords": ["php", "wordpress", "salesforce", "drupal"],
    "hours_since_posted": 4,
    "startup_only": False,
    "linkedin_time_filter": "r86400",
    "linkedin_remote_filter": "2",
    "linkedin_distance": "25",
    "naukri_experience": "",
    "naukri_salary_lakhs": "",
    "greenhouse_boards": [],
    "lever_slugs": [],
    "max_jobs_per_source": 15,
    "llm_api": "http://localhost:11434/api/generate",
    "llm_model": "gemma3",
    "llm_timeout": 90,
    "output_dir": "output",
    "resume_path": "resume.txt",
}


@dataclass
class SearchConfig:
    keywords: str = "Full Stack Engineer"
    location: str = "Remote"
    min_salary: int | None = None
    min_salary_lakhs: float | None = None
    remote_only: bool = True
    experience_level: str = "mid"
    exclude_keywords: list[str] = field(default_factory=lambda: ["php", "wordpress", "salesforce", "drupal"])
    hours_since_posted: int = 4
    startup_only: bool = False
    linkedin_time_filter: str = "r86400"
    linkedin_remote_filter: str = "2"
    linkedin_distance: str = "25"
    naukri_experience: str = ""
    naukri_salary_lakhs: str = ""
    greenhouse_boards: list[str] = field(default_factory=list)
    lever_slugs: list[str] = field(default_factory=list)
    max_jobs_per_source: int = 15
    llm_api: str = "http://localhost:11434/api/generate"
    llm_model: str = "gemma3"
    llm_timeout: int = 90
    output_dir: str = "output"
    resume_path: str = "resume.txt"

    def __post_init__(self):
        if isinstance(self.exclude_keywords, str):
            self.exclude_keywords = [k.strip() for k in self.exclude_keywords.split(",") if k.strip()]
        if isinstance(self.greenhouse_boards, str):
            self.greenhouse_boards = [k.strip() for k in self.greenhouse_boards.split(",") if k.strip()]
        if isinstance(self.lever_slugs, str):
            self.lever_slugs = [k.strip() for k in self.lever_slugs.split(",") if k.strip()]


def load_config(path: str | Path = "config.json") -> SearchConfig:
    """Load config from JSON. Creates a template file if missing."""
    path = Path(path)

    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        print(f"\n{'='*60}")
        print(f"Created default config at {path}")
        print("Edit it with your preferences, then run again.")
        print(f"{'='*60}\n")
        return SearchConfig()

    data = json.loads(path.read_text())
    # Merge with defaults so missing keys don't crash
    merged = {**DEFAULT_CONFIG, **data}
    return SearchConfig(**merged)
3. Replace src/cli.py entirely
Python
import argparse
import asyncio
import sys
from pathlib import Path

from src.aggregator import aggregate, save_results
from src.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Job Aggregator")
    parser.add_argument("--config", "-c", default="config.json", help="Path to config JSON")
    parser.add_argument("--keywords", "-k", default=None, help="Job keywords")
    parser.add_argument("--location", "-l", default=None, help="Location")
    parser.add_argument("--min-salary", type=int, default=None, help="Minimum salary (USD)")
    parser.add_argument("--min-lpa", type=float, default=None, help="Minimum salary in LPA")
    parser.add_argument("--experience", "-e", default=None, choices=["entry", "mid", "senior", "staff"])
    parser.add_argument("--exclude", default=None, help="Comma-separated excluded keywords")
    parser.add_argument("--time-filter", default=None, help="LinkedIn: r86400=24h, r604800=week")
    parser.add_argument("--hours", type=int, default=None, help="Only jobs posted within last N hours")
    parser.add_argument("--startup", action="store_true", default=None, help="Only startup jobs")
    parser.add_argument("--remote", action="store_true", default=None, help="Remote only")
    parser.add_argument("--no-remote", dest="remote", action="store_false", default=None, help="Include non-remote")
    parser.add_argument("--naukri-exp", default=None, help="Naukri experience filter (years)")
    parser.add_argument("--naukri-ctc", default=None, help="Naukri CTC filter e.g. 20to50")

    args = parser.parse_args()

    # Load config.json (creates template if missing)
    config = load_config(args.config)

    # Override with any CLI args that were explicitly provided
    if args.keywords is not None:
        config.keywords = args.keywords
    if args.location is not None:
        config.location = args.location
    if args.min_salary is not None:
        config.min_salary = args.min_salary
    if args.min_lpa is not None:
        config.min_salary_lakhs = args.min_lpa
    if args.experience is not None:
        config.experience_level = args.experience
    if args.exclude is not None:
        config.exclude_keywords = [k.strip() for k in args.exclude.split(",") if k.strip()]
    if args.time_filter is not None:
        config.linkedin_time_filter = args.time_filter
    if args.hours is not None:
        config.hours_since_posted = args.hours
    if args.startup is not None:
        config.startup_only = args.startup
    if args.remote is not None:
        config.remote_only = args.remote
    if args.naukri_exp is not None:
        config.naukri_experience = args.naukri_exp
    if args.naukri_ctc is not None:
        config.naukri_salary_lakhs = args.naukri_ctc

    if not Path(config.resume_path).exists():
        print(f"ERROR: Create {config.resume_path} with your profile first!")
        sys.exit(1)

    profile = Path(config.resume_path).read_text()

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

    save_results(jobs, config)

    print("\nNext: uv run python apply.py output/jobs_to_apply_*.txt")
4. Patch src/aggregator.py
Change the save_results signature and paths:
Python
def save_results(jobs: list[JobListing], config: SearchConfig, prefix: str = ""):
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    json_dir = Path(config.output_dir) / "jobs_found"
    txt_dir = Path(config.output_dir) / "jobs_to_apply"
    json_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    # ... rest unchanged
Replace the hardcoded Greenhouse / Lever lists with config values:
Python
        # Greenhouse
        for board in config.greenhouse_boards:
            context = await new_stealth_context(browser)
            page = await context.new_page()
            jobs = await GreenhouseSource.scrape(board, page)
            all_jobs.extend(jobs)
            await context.close()

        # Lever
        for slug in config.lever_slugs:
            context = await new_stealth_context(browser)
            page = await context.new_page()
            jobs = await LeverSource.scrape(slug, page)
            all_jobs.extend(jobs)
            await context.close()
Replace every hardcoded [:15] or [:20] limit with config.max_jobs_per_source:
In src/sources/linkedin.py: for i, card in enumerate(cards[:config.max_jobs_per_source]):
In src/sources/indeed.py: for card in cards[:config.max_jobs_per_source]:
In src/sources/naukri.py: for listing in listings[:config.max_jobs_per_source]:
In src/sources/wellfound.py: for listing in listings[:config.max_jobs_per_source]: and for link in all_links[:config.max_jobs_per_source]:
5. Patch src/llm.py
Update ask_llm to accept model and timeout:
Python
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
Update the call inside evaluate_job:
Python
        response = await ask_llm(prompt, model=config.llm_model, timeout=config.llm_timeout)
6. Patch src/apply.py (optional, keeps everything in one config)
Top of file:
Python
from src.aggregator import STEALTH_SCRIPT
from src.config import load_config
Update load_profile:
Python
def load_profile(resume_path: str = "resume.txt"):
    text = Path(resume_path).read_text()
    lines = text.strip().split("\n")
    name = lines[0] if lines else "Applicant"
    email = next((line for line in lines if "@" in line), "")
    phone = next((line for line in lines if any(c.isdigit() for c in line) and len(line) > 9), "")
    return {"name": name, "email": email, "phone": phone, "raw": text}
Update ask_llm:
Python
async def ask_llm(prompt: str, model: str = "gemma3", api: str = "http://localhost:11434/api/generate", timeout: int = 120) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(api, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        })
        return r.json().get("response", "").strip()
Update generate_answers:
Python
async def generate_answers(job, profile, config):
    prompt = f"""You are {profile['name']}. Write a brief, professional cover letter for this job:
...
Your profile:
{profile['raw'][:1000]}
...
Write 2-3 short paragraphs. Be specific, not generic. Mention relevant skills and experience."""

    cover_letter = await ask_llm(
        prompt,
        model=config.llm_model,
        api=config.llm_api,
        timeout=config.llm_timeout,
    )
    # ... rest unchanged
Update main():
Python
    config = load_config()
    if not Path(config.resume_path).exists():
        print(f"ERROR: Create {config.resume_path} with your profile first!")
        sys.exit(1)

    profile = load_profile(config.resume_path)
    print(f"Loaded profile for: {profile['name']}")
How to use it
First run — creates config.json automatically:
bash
uv run python -m src.cli
Edit config.json with your real preferences (e.g., set min_salary_lakhs to 15, hours_since_posted to 4, add company slugs to greenhouse_boards).
From then on, just run:
bash
uv run python -m src.cli
Override one thing for a single run (e.g., test with last 2 hours only):
bash
uv run python -m src.cli --hours 2 --startup
Use a different config file:
bash
uv run python -m src.cli --config ~/job-bot-config.json
That’s it. config.json is now the single source of truth. CLI flags are only for temporary overrides.