import logging
from datetime import datetime
from uuid import uuid4

from src.browser.engine import BrowserEngine
from src.models.job import Job
from src.sources.base import Source

logger = logging.getLogger("job-bot.sources.linkedin")

SEARCH_URL = "https://www.linkedin.com/jobs/search/"
JOB_CARD_SELECTOR = ".base-card, .job-search-card"
TITLE_SELECTOR = ".base-search-card__title, h3"
COMPANY_SELECTOR = ".base-search-card__subtitle, h4"
LOCATION_SELECTOR = ".job-search-card__location"
LINK_SELECTOR = "a.base-card__full-link, a[href*='/jobs/view/']"


class LinkedInSource(Source):
    def __init__(
        self,
        browser: BrowserEngine,
        keywords: list[str] | None = None,
        location: str | None = None,
    ) -> None:
        self._browser = browser
        self._keywords = keywords or []
        self._location = location

    async def discover(self) -> list[Job]:
        jobs: list[Job] = []
        for keyword in self._keywords:
            try:
                found = await self._search(keyword)
                jobs.extend(found)
            except Exception:
                logger.exception("Failed to search LinkedIn for: %s", keyword)
                await self._browser.screenshot("storage/screenshots/linkedin_error.png")
        logger.info(
            "Discovered %d jobs from LinkedIn (%d searches)",
            len(jobs),
            len(self._keywords),
        )
        return jobs

    async def _search(self, keyword: str) -> list[Job]:
        params = f"?keywords={keyword}"
        if self._location:
            params += f"&location={self._location}"
        url = f"{SEARCH_URL}{params}"

        await self._browser.navigate(url)

        try:
            await self._browser.wait_for(JOB_CARD_SELECTOR, timeout=15000)
        except Exception:
            logger.warning("No job cards found for LinkedIn search: %s", keyword)
            return []

        jobs_data = await self._browser.evaluate(
            """
            () => {
                const cards = document.querySelectorAll('.base-card, .job-search-card');
                return Array.from(cards).map(card => {
                    const titleEl = card.querySelector('h3, .base-search-card__title');
                    const companyEl = card.querySelector('h4, .base-search-card__subtitle');
                    const locationEl = card.querySelector('.job-search-card__location');
                    const linkEl = card.querySelector('a[href*="/jobs/view/"]');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        company: companyEl ? companyEl.textContent.trim() : '',
                        location: locationEl ? locationEl.textContent.trim() : null,
                        url: linkEl ? linkEl.href : null,
                    };
                });
            }
            """
        )

        if not isinstance(jobs_data, list):
            return []

        return [self._normalize(item, keyword) for item in jobs_data if self._is_valid(item)]

    def _is_valid(self, item: object) -> bool:
        if not isinstance(item, dict):
            return False
        return bool(item.get("title")) and bool(item.get("company"))

    def _normalize(self, item: dict, keyword: str) -> Job:
        return Job(
            id=str(uuid4()),
            source="linkedin",
            company=item.get("company", "Unknown"),
            title=item.get("title", "Unknown"),
            location=item.get("location"),
            description=f"LinkedIn search: {keyword}",
            apply_url=item.get("url"),
            posted_date=datetime.now(),
            metadata={"search_keyword": keyword},
        )
