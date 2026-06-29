import asyncio
import json
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from src.config import SearchConfig
from src.models import JobListing


class LinkedInSource:
    BASE_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    @staticmethod
    def build_search_url(config: SearchConfig, start: int = 0) -> str:
        params = {
            "keywords": quote_plus(config.keywords),
            "location": quote_plus(config.location),
            "start": start,
        }
        if config.linkedin_time_filter:
            params["f_TPR"] = config.linkedin_time_filter
        if config.remote_only:
            params["f_WT"] = "2"
        level_map = {"entry": "2", "mid": "4", "senior": "5", "staff": "6"}
        if config.experience_level in level_map:
            params["f_E"] = level_map[config.experience_level]
        return f"{LinkedInSource.BASE_SEARCH}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    @staticmethod
    async def _fetch_job_detail(client: httpx.AsyncClient, url: str) -> tuple[str, str | None]:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            script = soup.find("script", type="application/ld+json")
            if script:
                try:
                    ld = json.loads(script.string)
                    desc = ld.get("description", "")
                    salary = None
                    est = ld.get("estimatedSalary")
                    if isinstance(est, dict):
                        salary = est.get("name")
                    elif isinstance(est, list) and len(est) > 0:
                        salary = est[0].get("name")
                    return desc, salary
                except Exception:
                    pass

            desc_el = soup.select_one(
                ".description__text, .show-more-less-html__markup, div[class*='description']"
            )
            desc = desc_el.get_text(separator="\n", strip=True) if desc_el else ""
            return desc, None
        except Exception:
            return "", None

    @staticmethod
    async def scrape(config: SearchConfig) -> list[JobListing]:
        jobs: list[JobListing] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        async with httpx.AsyncClient(
            headers=headers, timeout=30, http2=True, follow_redirects=True
        ) as client:
            for start in range(0, config.max_jobs_per_source * 2, 25):
                url = LinkedInSource.build_search_url(config, start)
                print(f"  LinkedIn: {url[:90]}...")

                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        print(f"    LinkedIn returned {resp.status_code}, stopping.")
                        break

                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.find_all("li")
                    if not cards:
                        print("    No cards found, stopping.")
                        break

                    print(f"    Found {len(cards)} cards")

                    card_data = []
                    hrefs = []
                    for card in cards:
                        title_el = card.select_one("h3.base-search-card__title")
                        company_el = card.select_one("h4.base-search-card__subtitle")
                        loc_el = card.select_one("span.job-search-card__location")
                        link_el = card.select_one("a.base-card__full-link")
                        date_el = card.select_one("time")

                        if not title_el or not link_el:
                            continue

                        title = title_el.get_text(strip=True)
                        company = company_el.get_text(strip=True) if company_el else ""
                        location = loc_el.get_text(strip=True) if loc_el else ""
                        href = link_el.get("href", "").split("?")[0]
                        posted = date_el.get("datetime") if date_el else ""

                        card_data.append((title, company, location, href, posted))
                        hrefs.append(href)

                    sem = asyncio.Semaphore(5)
                    async def limited_fetch(href: str):
                        async with sem:
                            await asyncio.sleep(0.3)
                            return await LinkedInSource._fetch_job_detail(client, href)

                    details = await asyncio.gather(*[limited_fetch(h) for h in hrefs])

                    for (title, company, location, href, posted), (desc, salary) in zip(
                        card_data, details
                    ):
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=location,
                                url=href,
                                source="linkedin",
                                posted_date=posted,
                                description=desc,
                                salary=str(salary) if salary else None,
                            )
                        )

                    if len(cards) < 25:
                        break

                except Exception as e:
                    print(f"    LinkedIn error: {e}")
                    break

        print(f"    {len(jobs)} LinkedIn jobs")
        return jobs
