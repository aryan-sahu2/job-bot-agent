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
