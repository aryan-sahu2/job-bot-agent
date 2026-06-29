import httpx

from src.config import SearchConfig
from src.models import JobListing


class SmartRecruitersSource:
    @staticmethod
    async def scrape(company_id: str, config: SearchConfig) -> list[JobListing]:
        url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
        print(f"  SmartRecruiters: {url}")

        jobs: list[JobListing] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()

                for posting in data.get("content", []):
                    title = posting.get("name", "")
                    if not title:
                        continue

                    loc = posting.get("location", {})
                    if isinstance(loc, dict):
                        parts = [
                            loc.get("city", ""),
                            loc.get("region", ""),
                            loc.get("country", ""),
                        ]
                        location = ", ".join([p for p in parts if p])
                    else:
                        location = "Remote"

                    desc = ""
                    if isinstance(posting.get("jobAd"), dict):
                        desc = posting["jobAd"].get("description", "")

                    jobs.append(
                        JobListing(
                            title=title,
                            company=company_id.replace("-", " ").title(),
                            location=location or "Remote",
                            url=posting.get("ref", ""),
                            description=desc[:1000],
                            source="smartrecruiters",
                        )
                    )
                print(f"    {len(jobs)} SmartRecruiters jobs for {company_id}")

        except Exception as e:
            print(f"    SmartRecruiters error: {e}")

        return jobs
