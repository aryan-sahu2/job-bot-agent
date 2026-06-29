import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class NaukriSource:
    @staticmethod
    def build_url(config: SearchConfig) -> str:
        kw_slug = config.keywords.replace(" ", "-").lower()
        base = f"https://www.naukri.com/{kw_slug}-jobs"
        params: dict[str, str] = {"k": config.keywords}
        if config.naukri_experience:
            params["experience"] = config.naukri_experience
        if config.naukri_salary_lakhs:
            params["ctcFilter"] = config.naukri_salary_lakhs
        if config.remote_only:
            params["wfhType"] = "1"

        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{base}?{query}"

    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        url = NaukriSource.build_url(config)
        print(f"  Naukri: {url[:90]}...")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)

            # Scroll to force lazy-load render
            for _ in range(4):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Try multiple selectors because Naukri changes classes often
            listings = await page.query_selector_all(".srp-jobtuple-wrapper")
            if not listings:
                listings = await page.query_selector_all("article.jobTuple")
            if not listings:
                listings = await page.query_selector_all("div.jobTuple")
            if not listings:
                listings = await page.query_selector_all("[data-job-id]")

            print(f"    Found {len(listings)} listings")

            jobs: list[JobListing] = []
            for listing in listings[:config.max_jobs_per_source]:
                try:
                    title_el = await listing.query_selector(
                        "a.title, a[class*='title'], h2 a"
                    )
                    company_el = await listing.query_selector(
                        "a.comp-name, [class*='comp-name'], a[href*='/company/']"
                    )
                    loc_el = await listing.query_selector(
                        "span.locWdth, span[class*='loc'], div[class*='loc']"
                    )
                    desc_el = await listing.query_selector(
                        "span.job-desc, span[class*='desc']"
                    )
                    salary_el = await listing.query_selector(
                        "span.sal, span[class*='sal']"
                    )
                    exp_el = await listing.query_selector(
                        "span.expwdth, span[class*='exp']"
                    )

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""
                    description = await desc_el.inner_text() if desc_el else ""
                    salary = await salary_el.inner_text() if salary_el else ""
                    exp = await exp_el.inner_text() if exp_el else ""

                    if title and href:
                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.naukri.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title.strip(),
                                company=company.strip(),
                                location=(location.strip() or exp),
                                url=full_url,
                                salary=salary.strip() if salary else None,
                                description=description.strip(),
                                source="naukri",
                            )
                        )
                except Exception:
                    continue

            print(f"    {len(jobs)} Naukri jobs")
            return jobs

        except Exception as e:
            print(f"    Naukri error: {e}")
            return []
