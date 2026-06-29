import asyncio
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.config import SearchConfig
from src.models import JobListing


class IndeedSource:
    @staticmethod
    def build_url(config: SearchConfig, start: int = 0) -> str:
        base = "https://www.indeed.com/jobs"
        params = {
            "q": config.keywords,
            "l": config.location,
            "fromage": "1",
            "start": start,
        }
        if config.remote_only:
            params["sc"] = "0kf:attr(DSQF7);"
        query = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        jobs: list[JobListing] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with AsyncSession(impersonate="chrome124") as client:
            for start in range(0, config.max_jobs_per_source * 2, 15):
                url = IndeedSource.build_url(config, start)
                print(f"  Indeed: {url[:90]}...")

                try:
                    resp = await client.get(url, headers=headers, timeout=30)
                    if resp.status_code != 200:
                        print(f"    Indeed returned {resp.status_code}")
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Indeed job links always contain /rc/clk?jk= or /viewjob?jk=
                    job_links = soup.find_all(
                        "a", href=re.compile(r"/rc/clk\?jk=|/viewjob\?jk=")
                    )
                    print(f"    Found {len(job_links)} job links")

                    if not job_links:
                        break

                    seen = set()
                    for link in job_links[:config.max_jobs_per_source]:
                        href = link.get("href", "")
                        if not href or href in seen:
                            continue
                        seen.add(href)

                        title = link.get_text(strip=True)
                        if not title:
                            continue

                        # Walk up to find the card container
                        parent = link.find_parent(
                            "div",
                            class_=re.compile(
                                r"job_seen_beacon|slider_container|mosaic-provider-jobcard|jobCard"
                            ),
                        )

                        company = ""
                        location = ""
                        posted = ""
                        if parent:
                            comp_el = parent.select_one(
                                "[data-testid='company-name'], .companyName, span.company"
                            )
                            loc_el = parent.select_one(
                                "[data-testid='job-location'], div.companyLocation, span.location"
                            )
                            date_el = parent.select_one(
                                "span.date, span[data-testid='job-date']"
                            )
                            company = comp_el.get_text(strip=True) if comp_el else ""
                            location = loc_el.get_text(strip=True) if loc_el else ""
                            posted = date_el.get_text(strip=True) if date_el else ""

                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.indeed.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=location,
                                url=full_url,
                                source="indeed",
                                posted_date=posted,
                            )
                        )

                    if len(job_links) < 15:
                        break
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"    Indeed error: {e}")
                    break

        print(f"    {len(jobs)} Indeed jobs")
        return jobs
