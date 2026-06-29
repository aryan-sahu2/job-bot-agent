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
    parser.add_argument(
        "--experience", "-e", default=None,
        choices=["entry", "mid", "senior", "staff"],
    )
    parser.add_argument("--exclude", default=None, help="Comma-separated excluded keywords")
    parser.add_argument(
        "--time-filter", default=None,
        help="LinkedIn: r86400=24h, r604800=week",
    )
    parser.add_argument(
        "--hours", type=int, default=None,
        help="Only jobs posted within last N hours",
    )
    parser.add_argument("--startup", action="store_true", default=None, help="Only startup jobs")
    parser.add_argument("--remote", action="store_true", default=None, help="Remote only")
    parser.add_argument(
        "--no-remote", dest="remote", action="store_false",
        default=None, help="Include non-remote",
    )
    parser.add_argument("--naukri-exp", default=None, help="Naukri experience filter (years)")
    parser.add_argument("--naukri-ctc", default=None, help="Naukri CTC filter e.g. 20to50")

    args = parser.parse_args()

    config = load_config(args.config)

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
