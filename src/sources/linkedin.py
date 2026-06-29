import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class LinkedInSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        base = "https://www.linkedin.com/jobs/search"
        params = {
            "keywords": config.keywords,
            "location": config.location,
            "distance": config.linkedin_distance,
            "f_TPR": config.linkedin_time_filter,
        }
        if config.remote_only:
            params["f_WT"] = config.linkedin_remote_filter

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v)
        return f"{base}?{query}"

    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = LinkedInSource.build_url(config)
        print(f"  LinkedIn: {url[:90]}...")

        await page.goto(url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(4)

        jobs = []
        cards = await page.query_selector_all(".base-card")
        print(f"    Found {len(cards)} cards")

        for i, card in enumerate(cards[:15]):
            try:
                title_el = await card.query_selector(".base-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle")
                loc_el = await card.query_selector(".job-search-card__location")
                link_el = await card.query_selector("a.base-card__full-link")
                date_el = await card.query_selector("time")

                title = await title_el.inner_text() if title_el else ""
                company = await company_el.inner_text() if company_el else ""
                location = await loc_el.inner_text() if loc_el else ""
                href = await link_el.get_attribute("href") if link_el else ""
                posted = await date_el.get_attribute("datetime") if date_el else ""

                if not title or not href:
                    continue

                clean_url = href.split("?")[0]

                description = ""
                salary = None
                try:
                    new_page = await page.context.new_page()
                    await new_page.goto(clean_url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)

                    desc_el = await new_page.query_selector(
                        ".description__text, .show-more-less-html__markup, [class*='description']"
                    )
                    if desc_el:
                        description = await desc_el.inner_text()

                    salary_el = await new_page.query_selector(
                        ".compensation__salary, [class*='salary'], [class*='compensation']"
                    )
                    salary = await salary_el.inner_text() if salary_el else None

                    await new_page.close()
                except Exception as e:
                    print(f"    Skip desc fetch for {title[:30]}: {e}")

                jobs.append(JobListing(
                    title=title.strip(),
                    company=company.strip(),
                    location=location.strip(),
                    url=clean_url,
                    salary=salary,
                    description=description.strip(),
                    source="linkedin",
                    posted_date=posted,
                ))

                await asyncio.sleep(1.5)

            except Exception as e:
                print(f"    Card parse error: {e}")
                continue

        print(f"    {len(jobs)} LinkedIn jobs with descriptions")
        return jobs
