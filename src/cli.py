import argparse
import asyncio
import sys
from pathlib import Path

from src.aggregator import aggregate, save_results
from src.config import SearchConfig


def main():
    parser = argparse.ArgumentParser(description="Job Aggregator")
    parser.add_argument("--keywords", "-k", default="Full Stack Engineer", help="Job keywords")
    parser.add_argument("--location", "-l", default="Remote", help="Location")
    parser.add_argument("--min-salary", type=int, default=None, help="Minimum salary (USD)")
    parser.add_argument("--experience", "-e", default="mid",
                        choices=["entry", "mid", "senior", "staff"])
    parser.add_argument("--exclude", default="php,wordpress,salesforce",
                        help="Comma-separated excluded keywords")
    parser.add_argument("--time-filter", default="r6400",
                        help="LinkedIn: r6400=2h, r86400=24h, r604800=week")
    parser.add_argument("--remote", action="store_true", default=True,
                        help="Remote only")
    parser.add_argument("--no-remote", dest="remote", action="store_false",
                        help="Include non-remote")
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
