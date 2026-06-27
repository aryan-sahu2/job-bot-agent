import asyncio
import logging
import signal
from datetime import datetime
from uuid import uuid4

from src.config.loader import SchedulerConfig
from src.evaluator.evaluator import JobEvaluator
from src.models.application import Application
from src.models.job import Job
from src.profile.models import Profile
from src.sources.base import Source
from src.storage.database import Database
from src.workflow.answer import AnswerGenerator

logger = logging.getLogger("job-bot.scheduler")


class Scheduler:
    def __init__(
        self,
        sources: list[Source],
        database: Database,
        evaluator: JobEvaluator,
        answer_generator: AnswerGenerator,
        profile: Profile,
        config: SchedulerConfig,
    ) -> None:
        self._sources = sources
        self._db = database
        self._evaluator = evaluator
        self._answer_gen = answer_generator
        self._profile = profile
        self._config = config
        self._running = False
        self._last_run: datetime | None = None

    @property
    def last_run(self) -> datetime | None:
        return self._last_run

    async def run_once(self) -> list[Application]:
        logger.info("Starting scan cycle")
        self._last_run = datetime.now()

        all_jobs: list[Job] = []
        for source in self._sources:
            try:
                jobs = await source.discover()
                all_jobs.extend(jobs)
            except Exception:
                logger.exception("Source %s failed during discovery", type(source).__name__)

        new_jobs = self._deduplicate(all_jobs)
        if self._config.max_jobs_per_run > 0:
            new_jobs = new_jobs[: self._config.max_jobs_per_run]

        logger.info("Discovered %d new jobs (of %d total)", len(new_jobs), len(all_jobs))

        applications: list[Application] = []
        for job in new_jobs:
            try:
                app = await self._process_job(job)
                applications.append(app)
            except Exception:
                logger.exception("Failed to process job %s at %s", job.title, job.company)

        logger.info("Scan cycle complete: %d applications queued for review", len(applications))
        return applications

    async def run_forever(self) -> None:
        self._running = True
        self._install_signal_handlers()

        logger.info(
            "Scheduler started | interval=%dmin max_jobs=%d",
            self._config.interval_minutes,
            self._config.max_jobs_per_run,
        )

        while self._running:
            await self.run_once()
            if self._running:
                logger.info("Sleeping for %d minutes", self._config.interval_minutes)
                await asyncio.sleep(self._config.interval_minutes * 60)

        logger.info("Scheduler stopped")

    def stop(self) -> None:
        self._running = False

    def _deduplicate(self, jobs: list[Job]) -> list[Job]:
        existing = {j.id for j in self._db.list_jobs()}
        seen: set[str] = set()
        unique: list[Job] = []

        for job in jobs:
            if job.id not in existing and job.id not in seen:
                seen.add(job.id)
                unique.append(job)

        return unique

    async def _process_job(self, job: Job) -> Application:
        self._db.save_job(job)

        evaluation = await self._evaluator.evaluate(job, self._profile)
        logger.info(
            "Evaluated %s at %s | score=%d",
            job.title,
            job.company,
            evaluation.match_score,
        )

        answer = await self._answer_gen.generate(job, self._profile)

        app = Application(
            id=str(uuid4()),
            job_id=job.id,
            answers={"cover_letter": answer},
        )
        self._db.save_application(app)

        logger.info(
            "Application %s queued | company=%s role=%s",
            app.id,
            job.company,
            job.title,
        )
        return app

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.stop)
