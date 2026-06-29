import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class IndeedSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        base = "https://www.indeed.com/jobs"
        params = {
            "q": config.keywords,
            "l": config.location,
            "fromage": "1" if config.linkedin_time_filter.startswith("r") else "7",
        }
        if config.remote_only:
            params["sc"] = "0kf:attr(DSQF7);"

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = IndeedSource.build_url(config)
        print(f"  Indeed: {url[:90]}...")

        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)

            jobs = []
            cards = await page.query_selector_all(
                ".job_seen_beacon, [data-testid='jobTitle-click']"
            )

            for card in cards[:15]:
                try:
                    title_el = await card.query_selector("h2 a, .jobTitle, a[id*='job_']")
                    company_el = await card.query_selector(
                        ".companyName, [data-testid='company-name']"
                    )
                    loc_el = await card.query_selector("[data-testid='job-location']")

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""

                    if title and href:
                        full_url = href if href.startswith("http") else f"https://www.indeed.com{href}"
                        jobs.append(JobListing(
                            title=title.strip(),
                            company=company.strip(),
                            location=location.strip(),
                            url=full_url,
                            source="indeed",
                        ))
                except Exception:
                    continue

            print(f"    {len(jobs)} Indeed jobs")
            return jobs

        except Exception as e:
            print(f"    Indeed error: {e}")
            return []
