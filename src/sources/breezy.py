import httpx

from src.config import SearchConfig
from src.models import JobListing


class BreezySource:
    @staticmethod
    async def scrape(company_slug: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://{company_slug}.breezy.hr/json"
        print(f"  Breezy: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                data = resp.json()

                for job in data:
                    title = job.get("name", "")
                    if not title:
                        continue

                    loc = job.get("location", {})
                    if isinstance(loc, dict):
                        location = loc.get("name", "Remote")
                    elif isinstance(loc, list) and len(loc) > 0:
                        location = (
                            loc[0].get("name", "Remote")
                            if isinstance(loc[0], dict)
                            else str(loc[0])
                        )
                    else:
                        location = "Remote"

                    jobs.append(
                        JobListing(
                            title=title,
                            company=company_slug.replace("-", " ").title(),
                            location=str(location),
                            url=job.get("url", ""),
                            description=job.get("description", "")[:1000],
                            source="breezy",
                        )
                    )
                print(f"    {len(jobs)} Breezy jobs for {company_slug}")

        except Exception as e:
            print(f"    Breezy error: {e}")

        return jobs
