import logging
from datetime import datetime

from src.browser.engine import BrowserEngine
from src.models.application import Application
from src.models.forms import FormField
from src.models.job import Job
from src.storage.database import Database
from src.workflow.form_filler import FormFiller

logger = logging.getLogger("job-bot.submitter")


class SubmissionError(Exception):
    pass


class Submitter:
    def __init__(
        self,
        database: Database,
        browser: BrowserEngine,
        form_filler: FormFiller,
    ):
        self._db = database
        self._browser = browser
        self._form_filler = form_filler

    async def submit(
        self,
        application: Application,
        job: Job,
        form_fields: list[FormField],
        submit_selector: str,
    ) -> None:
        if application.status != "approved":
            raise SubmissionError(
                f"Cannot submit application {application.id}: "
                f"status is '{application.status}', expected 'approved'"
            )

        if not job.apply_url:
            raise SubmissionError(
                f"Cannot submit application {application.id}: "
                f"job {job.id} has no apply URL"
            )

        await self._browser.navigate(job.apply_url)
        await self._form_filler.fill_fields(form_fields)
        await self._browser.click(submit_selector)

        now = datetime.now()
        application.status = "submitted"
        application.submitted_at = now
        self._db.save_application(application)

        logger.info(
            "Application submitted | timestamp=%s company=%s role=%s source=%s status=%s",
            now.isoformat(),
            job.company,
            job.title,
            job.source,
            application.status,
        )
