import httpx

from src.config import SearchConfig
from src.models import JobListing


class GreenhouseSource:
    @staticmethod
    async def scrape(board_slug: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://api.greenhouse.io/v1/boards/{board_slug}/jobs?content=true"
        print(f"  Greenhouse: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                for job in data.get("jobs", []):
                    locs = ", ".join([loc["name"] for loc in job.get("locations", [])])
                    jobs.append(
                        JobListing(
                            title=job.get("title", ""),
                            company=board_slug.replace("-", " ").title(),
                            location=locs,
                            url=job.get("absolute_url", ""),
                            description=job.get("content", ""),
                            source="greenhouse",
                        )
                    )
                print(f"    {len(jobs)} Greenhouse jobs for {board_slug}")

        except Exception as e:
            print(f"    Greenhouse error: {e}")

        return jobs
