import httpx

from src.config import SearchConfig
from src.models import JobListing


class LeverSource:
    @staticmethod
    async def scrape(company_slug: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
        print(f"  Lever: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

                for posting in data:
                    cats = posting.get("categories", {})
                    loc = cats.get("location", "") if isinstance(cats, dict) else ""
                    if not loc:
                        loc = posting.get("location", "")

                    jobs.append(
                        JobListing(
                            title=posting.get("text", ""),
                            company=company_slug.replace("-", " ").title(),
                            location=loc,
                            url=posting.get("hostedUrl", ""),
                            description=posting.get("description", ""),
                            source="lever",
                        )
                    )
                print(f"    {len(jobs)} Lever jobs for {company_slug}")

        except Exception as e:
            print(f"    Lever error: {e}")

        return jobs
