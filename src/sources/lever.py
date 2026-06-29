from playwright.async_api import Page

from src.models import JobListing


class LeverSource:
    @staticmethod
    async def scrape(company_slug: str, page: Page) -> list[JobListing]:
        url = f"https://jobs.lever.co/{company_slug}"
        print(f"  Lever: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)

            jobs = []
            listings = await page.query_selector_all(".posting")

            for listing in listings:
                title_el = await listing.query_selector("h5[data-qa='posting-title']")
                if not title_el:
                    title_el = await listing.query_selector(".posting-title")

                if not title_el:
                    continue

                title = await title_el.inner_text()
                link_el = await listing.query_selector("a")
                href = await link_el.get_attribute("href") if link_el else ""

                loc_el = await listing.query_selector(".sort-by-time, .posting-category")
                location = await loc_el.inner_text() if loc_el else ""

                if title and href:
                    jobs.append(JobListing(
                        title=title.strip(),
                        company=company_slug.replace("-", " ").title(),
                        location=location.strip(),
                        url=href,
                        source="lever",
                    ))

            print(f"    {len(jobs)} Lever jobs for {company_slug}")
            return jobs

        except Exception as e:
            print(f"    Lever error: {e}")
            return []
