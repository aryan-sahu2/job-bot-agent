import httpx

from src.config import SearchConfig
from src.models import JobListing


class RecruiteeSource:
    @staticmethod
    async def scrape(company_slug: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://{company_slug}.recruitee.com/api/offers"
        print(f"  Recruitee: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()

                for offer in data.get("offers", []):
                    title = offer.get("title", "")
                    if not title:
                        continue

                    loc = offer.get("location", "")
                    if isinstance(loc, dict):
                        location = loc.get("city", "") or "Remote"
                    elif isinstance(loc, list) and len(loc) > 0:
                        location = (
                            loc[0].get("city", "")
                            if isinstance(loc[0], dict)
                            else str(loc[0])
                        )
                    else:
                        location = "Remote"

                    job_url = offer.get("careers_url") or offer.get("url", "")
                    jobs.append(
                        JobListing(
                            title=title,
                            company=company_slug.replace("-", " ").title(),
                            location=str(location),
                            url=job_url,
                            description=offer.get("description", "")[:1000],
                            source="recruitee",
                        )
                    )
                print(f"    {len(jobs)} Recruitee jobs for {company_slug}")

        except Exception as e:
            print(f"    Recruitee error: {e}")

        return jobs
