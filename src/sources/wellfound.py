import logging
from datetime import datetime
from uuid import uuid4

from src.browser.engine import BrowserEngine
from src.models.job import Job
from src.sources.base import Source

logger = logging.getLogger("job-bot.sources.wellfound")

JOB_CARD_SELECTOR = "[data-test='startup-card'], .startup-card, .job-card"
TITLE_SELECTOR = "[data-test='role-title'], .role-title, h3 a"
COMPANY_SELECTOR = "[data-test='company-name'], .company-name"
LOCATION_SELECTOR = "[data-test='location'], .location"
SALARY_SELECTOR = "[data-test='salary'], .salary"
DESCRIPTION_SELECTOR = "[data-test='description'], .description, .role-description"


class WellfoundSource(Source):
    def __init__(self, browser: BrowserEngine) -> None:
        self._browser = browser
        self._base_url = "https://wellfound.com"

    async def discover(self) -> list[Job]:
        jobs: list[Job] = []
        url = f"{self._base_url}/jobs"

        try:
            await self._browser.navigate(url)
            await self._browser.wait_for(JOB_CARD_SELECTOR, timeout=15000)

            jobs_data = await self._browser.evaluate(
                """
                () => {
                    const sel = {
                        card: '[data-test="startup-card"], .startup-card',
                        title: '[data-test="role-title"], .role-title',
                        company: '[data-test="company-name"], .company-name',
                        location: '[data-test="location"], .location',
                        salary: '[data-test="salary"], .salary',
                        desc: '[data-test="description"], .description',
                    };
                    const cards = document.querySelectorAll(sel.card);
                    return Array.from(cards).map(card => {
                        const titleEl = card.querySelector(sel.title);
                        const companyEl = card.querySelector(sel.company);
                        const locationEl = card.querySelector(sel.location);
                        const salaryEl = card.querySelector(sel.salary);
                        const descEl = card.querySelector(sel.desc);
                        const linkEl = card.querySelector('a[href*="/jobs/"]');
                        return {
                            title: titleEl ? titleEl.textContent.trim() : '',
                            company: companyEl ? companyEl.textContent.trim() : '',
                            location: locationEl ? locationEl.textContent.trim() : null,
                            salary: salaryEl ? salaryEl.textContent.trim() : null,
                            description: descEl ? descEl.textContent.trim() : '',
                            url: linkEl ? linkEl.href : null,
                        };
                    });
                }
                """,
            )

            if not isinstance(jobs_data, list):
                logger.warning("Unexpected response format from Wellfound")
                return jobs

            for item in jobs_data:
                if not self._is_valid_job(item):
                    continue
                job = self._normalize(item)
                jobs.append(job)

            logger.info("Discovered %d jobs from Wellfound", len(jobs))

        except Exception:
            logger.exception("Failed to discover jobs from Wellfound")
            await self._browser.screenshot("storage/screenshots/wellfound_error.png")

        return jobs

    def _is_valid_job(self, item: object) -> bool:
        if not isinstance(item, dict):
            return False
        title = item.get("title", "")
        company = item.get("company", "")
        return bool(title) and bool(company)

    def _normalize(self, item: dict) -> Job:
        description = item.get("description", "")
        return Job(
            id=str(uuid4()),
            source="wellfound",
            company=item.get("company", "Unknown"),
            title=item.get("title", "Unknown"),
            location=item.get("location"),
            salary=item.get("salary"),
            description=description or "No description available",
            apply_url=item.get("url"),
            posted_date=datetime.now(),
            metadata={"raw_item": item},
        )
