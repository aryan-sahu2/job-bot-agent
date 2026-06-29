import asyncio
from urllib.parse import quote

from playwright.async_api import Page

from src.config import SearchConfig
from src.models import JobListing


class WellfoundSource:
    @staticmethod
    async def scrape(page: Page, config: SearchConfig) -> list[JobListing]:
        # Wellfound expects slugified roles like "full-stack-engineer"
        roles = quote(config.keywords.replace(" ", "-").lower())
        url = f"https://wellfound.com/jobs?roles={roles}"
        if config.location and config.location.lower() != "remote":
            url += f"&location={quote(config.location)}"
        print(f"  Wellfound: {url[:90]}...")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(5)

            # Infinite scroll
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            jobs: list[JobListing] = []
            seen_hrefs: set[str] = set()

            # Try structured cards first
            listings = await page.query_selector_all("[data-test='job-listing']")
            if not listings:
                listings = await page.query_selector_all("[data-testid='job-listing']")

            if listings:
                for listing in listings[:config.max_jobs_per_source]:
                    try:
                        link_el = await listing.query_selector("a[href*='/jobs/']")
                        if not link_el:
                            continue

                        href = await link_el.get_attribute("href")
                        if not href or href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)

                        text = await link_el.inner_text()
                        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                        title = lines[0] if lines else ""
                        company = lines[1] if len(lines) > 1 else ""

                        comp_el = await listing.query_selector(
                            "[data-test='company-name'], [class*='company']"
                        )
                        if comp_el:
                            company = await comp_el.inner_text()

                        full_url = (
                            href if href.startswith("http") else f"https://wellfound.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company.strip(),
                                location=config.location,
                                url=full_url,
                                source="wellfound",
                            )
                        )
                    except Exception:
                        continue
            else:
                # Fallback: grab every job link on the page
                all_links = await page.query_selector_all("a[href*='/jobs/']")
                for link in all_links[:config.max_jobs_per_source]:
                    try:
                        href = await link.get_attribute("href")
                        if not href or href in seen_hrefs:
                            continue
                        seen_hrefs.add(href)

                        text = await link.inner_text()
                        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                        if not lines:
                            continue

                        title = lines[0]
                        company = lines[1] if len(lines) > 1 else ""

                        full_url = (
                            href if href.startswith("http") else f"https://wellfound.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title,
                                company=company,
                                location=config.location,
                                url=full_url,
                                source="wellfound",
                            )
                        )
                    except Exception:
                        continue

            print(f"    {len(jobs)} Wellfound jobs")
            return jobs

        except Exception as e:
            print(f"    Wellfound error: {e}")
            return []
