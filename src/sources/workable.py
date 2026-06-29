import httpx

from src.config import SearchConfig
from src.models import JobListing


class WorkableSource:
    @staticmethod
    async def scrape(account: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://www.workable.com/api/accounts/{account}/jobs"
        print(f"  Workable: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()

                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    if not title:
                        continue

                    locs = job.get("locations", [])
                    if locs and isinstance(locs, list):
                        location = ", ".join(
                            [
                                loc.get("location_str", "")
                                for loc in locs
                                if isinstance(loc, dict)
                            ]
                        )
                    else:
                        location = "Remote"

                    jobs.append(
                        JobListing(
                            title=title,
                            company=account.replace("-", " ").title(),
                            location=location or "Remote",
                            url=job.get("url", ""),
                            description=(
                                job.get("description", "")
                                or job.get("requirements", "")
                            )[:1000],
                            source="workable",
                        )
                    )
                print(f"    {len(jobs)} Workable jobs for {account}")

        except Exception as e:
            print(f"    Workable error: {e}")

        return jobs
