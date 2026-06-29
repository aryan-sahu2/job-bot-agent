from playwright.async_api import Page

from src.models import JobListing


class GreenhouseSource:
    @staticmethod
    async def scrape(board_slug: str, page: Page) -> list[JobListing]:
        url = f"https://boards.greenhouse.io/{board_slug}"
        print(f"  Greenhouse: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)

            jobs = []
            listings = await page.query_selector_all(".opening")

            for listing in listings:
                title_el = await listing.query_selector("a")
                if not title_el:
                    continue

                title = await title_el.inner_text()
                href = await title_el.get_attribute("href")

                loc_el = await listing.query_selector(".location")
                location = await loc_el.inner_text() if loc_el else ""

                if title and href:
                    full_url = href if href.startswith("http") else f"https://boards.greenhouse.io{href}"
                    jobs.append(JobListing(
                        title=title.strip(),
                        company=board_slug.replace("-", " ").title(),
                        location=location.strip(),
                        url=full_url,
                        source="greenhouse",
                    ))

            print(f"    {len(jobs)} Greenhouse jobs for {board_slug}")
            return jobs

        except Exception as e:
            print(f"    Greenhouse error: {e}")
            return []
