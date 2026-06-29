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
            "fromage": "1",  # last 24 hours
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
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

            # Dismiss cookie/consent dialogs (EU / US variants)
            for btn_text in ["Accept", "Accept all", "Skip", "Continue"]:
                try:
                    btn = await page.query_selector(
                        f"button:has-text('{btn_text}'), "
                        f"button#onetrust-accept-btn-handler, "
                        f".gnav-CookieConsentButton"
                    )
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    pass

            # Scroll to load more results
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Multiple fallback selectors for job cards
            cards = await page.query_selector_all(".job_seen_beacon")
            if not cards:
                cards = await page.query_selector_all("div.slider_container")
            if not cards:
                cards = await page.query_selector_all("div[data-testid='jobTitle-click']")
            if not cards:
                cards = await page.query_selector_all("div.mosaic-provider-jobcard")

            print(f"    Found {len(cards)} cards")

            jobs: list[JobListing] = []
            for card in cards[:config.max_jobs_per_source]:
                try:
                    title_el = await card.query_selector(
                        "h2 a, a.jcs-JobTitle, .jobTitle a, a[id*='job_']"
                    )
                    company_el = await card.query_selector(
                        ".companyName, [data-testid='company-name'], span.company"
                    )
                    loc_el = await card.query_selector(
                        "[data-testid='job-location'], div.companyLocation, span.location"
                    )

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    location = await loc_el.inner_text() if loc_el else ""

                    date_el = await card.query_selector(
                        "span.date, span[data-testid='job-date'], span.date"
                    )
                    posted = await date_el.inner_text() if date_el else ""

                    if title and href:
                        full_url = (
                            href
                            if href.startswith("http")
                            else f"https://www.indeed.com{href}"
                        )
                        jobs.append(
                            JobListing(
                                title=title.strip(),
                                company=company.strip(),
                                location=location.strip(),
                                url=full_url,
                                source="indeed",
                                posted_date=posted,
                            )
                        )
                except Exception:
                    continue

            print(f"    {len(jobs)} Indeed jobs")
            return jobs

        except Exception as e:
            print(f"    Indeed error: {e}")
            return []
