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
