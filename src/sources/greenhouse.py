import logging
from datetime import datetime
from uuid import uuid4

from src.browser.engine import BrowserEngine
from src.models.job import Job
from src.sources.base import Source

logger = logging.getLogger("job-bot.sources.greenhouse")

DEPARTMENT_SELECTOR = ".department"
POSITION_SELECTOR = ".position"
TITLE_SELECTOR = ".app-title"
LOCATION_SELECTOR = ".app-location"
DESCRIPTION_SELECTOR = ".content-intro"


class GreenhouseSource(Source):
    def __init__(self, browser: BrowserEngine, board_slugs: list[str] | None = None) -> None:
        self._browser = browser
        self._board_slugs = board_slugs or []

    async def discover(self) -> list[Job]:
        jobs: list[Job] = []
        for slug in self._board_slugs:
            try:
                found = await self._scrape_board(slug)
                jobs.extend(found)
            except Exception:
                logger.exception("Failed to scrape Greenhouse board: %s", slug)
                await self._browser.screenshot(f"storage/screenshots/greenhouse_{slug}_error.png")
        logger.info(
            "Discovered %d jobs from Greenhouse (%d boards)",
            len(jobs),
            len(self._board_slugs),
        )
        return jobs

    async def _scrape_board(self, slug: str) -> list[Job]:
        url = f"https://boards.greenhouse.io/{slug}"
        await self._browser.navigate(url)

        try:
            await self._browser.wait_for(DEPARTMENT_SELECTOR, timeout=15000)
        except Exception:
            logger.warning("No department sections found on %s, trying flat listing", slug)

        jobs_data = await self._browser.evaluate(
            """
            () => {
                const jobs = [];
                const departments = document.querySelectorAll('.department');
                if (departments.length > 0) {
                    for (const dept of departments) {
                        const deptName =
                            dept.querySelector('.dept-name')
                                ?.textContent?.trim() || '';
                        const positions = dept.querySelectorAll('.position');
                        for (const pos of positions) {
                            const titleEl = pos.querySelector('.app-title a');
                            const locationEl = pos.querySelector('.app-location');
                            if (titleEl) {
                                jobs.push({
                                    title: titleEl.textContent.trim(),
                                    location: locationEl ? locationEl.textContent.trim() : null,
                                    url: titleEl.href || null,
                                    department: deptName,
                                });
                            }
                        }
                    }
                } else {
                    const rows = document.querySelectorAll('tr[data-department], .opening');
                    for (const row of rows) {
                        const titleEl = row.querySelector('a');
                        const locationEl = row.querySelector('.location');
                        if (titleEl) {
                            jobs.push({
                                title: titleEl.textContent.trim(),
                                location: locationEl ? locationEl.textContent.trim() : null,
                                url: titleEl.href || null,
                                department: null,
                            });
                        }
                    }
                }
                return jobs;
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
            source="greenhouse",
            company=slug.replace("-", " ").title(),
            title=item.get("title", "Unknown"),
            location=item.get("location"),
            description=item.get("department") or "No description available",
            apply_url=item.get("url"),
            posted_date=datetime.now(),
            metadata={"board_slug": slug, "department": item.get("department")},
        )
