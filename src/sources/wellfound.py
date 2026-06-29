import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class WellfoundSource:
    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = f"https://wellfound.com/jobs?roles={quote(config.keywords)}&location={quote(config.location)}"
        print("  Wellfound...")

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            jobs = []
            listings = await page.query_selector_all("[data-test='job-listing']")
            if not listings:
                listings = await page.query_selector_all(".styles_jobListing__")

            for listing in listings[:15]:
                try:
                    title_el = await listing.query_selector("[data-test='role-title']")
                    company_el = await listing.query_selector("[data-test='company-name']")
                    link_el = await listing.query_selector("a")

                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""

                    if title and href:
                        full_url = href if href.startswith("http") else f"https://wellfound.com{href}"
                        jobs.append(JobListing(
                            title=title.strip(),
                            company=company.strip(),
                            location=config.location,
                            url=full_url,
                            source="wellfound",
                        ))
                except Exception:
                    continue

            print(f"    {len(jobs)} Wellfound jobs")
            return jobs

        except Exception as e:
            print(f"    Wellfound error: {e}")
            return []
