import logging
from datetime import datetime
from uuid import uuid4

from src.browser.engine import BrowserEngine
from src.models.job import Job
from src.sources.base import Source

logger = logging.getLogger("job-bot.sources.lever")

POSTING_SELECTOR = ".posting"
TITLE_SELECTOR = ".posting-title"
TEAM_SELECTOR = ".posting-team"
LOCATION_SELECTOR = ".posting-categories .category"
DESCRIPTION_SELECTOR = ".posting-page .content, .posting-description"


class LeverSource(Source):
    def __init__(self, browser: BrowserEngine, company_slugs: list[str] | None = None) -> None:
        self._browser = browser
        self._company_slugs = company_slugs or []

    async def discover(self) -> list[Job]:
        jobs: list[Job] = []
        for slug in self._company_slugs:
            try:
                found = await self._scrape_company(slug)
                jobs.extend(found)
            except Exception:
                logger.exception("Failed to scrape Lever company: %s", slug)
                await self._browser.screenshot(
                    f"storage/screenshots/lever_{slug}_error.png"
                )
        logger.info(
            "Discovered %d jobs from Lever (%d companies)",
            len(jobs),
            len(self._company_slugs),
        )
        return jobs

    async def _scrape_company(self, slug: str) -> list[Job]:
        url = f"https://jobs.lever.co/{slug}"
        await self._browser.navigate(url)
        await self._browser.wait_for(POSTING_SELECTOR, timeout=15000)

        jobs_data = await self._browser.evaluate(
            """
            () => {
                const postings = document.querySelectorAll('.posting');
                return Array.from(postings).map(posting => {
                    const titleEl = posting.querySelector('.posting-title');
                    const teamEl = posting.querySelector('.posting-team');
                    const locationEl = posting.querySelector('.posting-categories .category');
                    const linkEl = posting.querySelector('a[data-qa]');
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        team: teamEl ? teamEl.textContent.trim() : null,
                        location: locationEl ? locationEl.textContent.trim() : null,
                        url: linkEl ? linkEl.href : null,
                    };
                });
            }
            """
        )

        if not isinstance(jobs_data, list):
            return []

        return [self._normalize(item, slug) for item in jobs_data if self._is_valid(item)]

    def _is_valid(self, item: object) -> bool:
        return isinstance(item, dict) and bool(item.get("title"))

    def _normalize(self, item: dict, slug: str) -> Job:
        return Job(
            id=str(uuid4()),
            source="lever",
            company=slug.replace("-", " ").title(),
            title=item.get("title", "Unknown"),
            location=item.get("location"),
            description=item.get("team") or "No description available",
            apply_url=item.get("url"),
            posted_date=datetime.now(),
            metadata={"company_slug": slug, "team": item.get("team")},
        )
