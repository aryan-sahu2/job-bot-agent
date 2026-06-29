import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config.loader import SchedulerConfig
from src.models.application import Application
from src.models.evaluation import Evaluation
from src.models.job import Job
from src.profile.models import Profile
from src.scheduler.scheduler import Scheduler
from src.sources.base import Source
from src.storage.database import Database


class MockSource(Source):
    def __init__(self, jobs: list[Job] | None = None, fail: bool = False):
        self._jobs = jobs or []
        self._fail = fail
        self.discover_count = 0

    async def discover(self) -> list[Job]:
        self.discover_count += 1
        if self._fail:
            raise Exception("Source failed")
        return list(self._jobs)


SAMPLE_JOB = Job(
    id="sched-job-1",
    source="wellfound",
    company="Test Corp",
    title="Backend Engineer",
    location="Remote",
    description="Build backend services.",
    apply_url="https://example.com/apply",
)

SAMPLE_PROFILE = Profile(
    name="Test User",
    skills=["Python", "Go"],
)


def _make_config(**overrides: object) -> SchedulerConfig:
    defaults = {"enabled": True, "interval_minutes": 60, "max_jobs_per_run": 50}
    defaults.update(overrides)
    return SchedulerConfig(**defaults)  # type: ignore[arg-type]


def _make_db() -> Database:
    tmp = tempfile.mktemp(suffix=".db")
    db = Database(tmp)
    db.initialize()
    return db


def _make_evaluator(evaluation: Evaluation | None = None) -> MagicMock:
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(
        return_value=evaluation
        or Evaluation(
            job_id="",
            match_score=80,
            strengths=["Good fit"],
            missing_skills=["AWS"],
            summary="Strong match.",
        )
    )
    return evaluator


def _make_answer_gen(answer: str = "Generated cover letter") -> MagicMock:
    gen = MagicMock()
    gen.generate = AsyncMock(return_value=answer)
    return gen


class TestSchedulerInit:
    def test_creates_with_config(self):
        db = _make_db()
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        assert scheduler.last_run is None
        db.close()


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_discovers_jobs_from_all_sources(self):
        db = _make_db()
        source = MockSource(jobs=[SAMPLE_JOB])
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        apps = await scheduler.run_once()

        assert source.discover_count == 1
        assert len(apps) == 1
        assert isinstance(apps[0], Application)
        db.close()

    @pytest.mark.asyncio
    async def test_deduplicates_jobs(self):
        db = _make_db()
        job1 = Job(id="dup-1", source="a", company="A", title="T", description="D")
        job2 = Job(id="dup-1", source="b", company="B", title="T2", description="D2")
        source = MockSource(jobs=[job1, job2])

        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        apps = await scheduler.run_once()

        assert len(apps) == 1
        db.close()

    @pytest.mark.asyncio
    async def test_skips_existing_jobs(self):
        db = _make_db()
        db.save_job(SAMPLE_JOB)

        source = MockSource(jobs=[SAMPLE_JOB])
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        apps = await scheduler.run_once()

        assert len(apps) == 0
        db.close()

    @pytest.mark.asyncio
    async def test_respects_max_jobs_per_run(self):
        db = _make_db()
        jobs = [
            Job(id=f"j-{i}", source="s", company="C", title=f"Job {i}", description="D")
            for i in range(10)
        ]
        source = MockSource(jobs=jobs)
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(max_jobs_per_run=3),
        )

        apps = await scheduler.run_once()

        assert len(apps) == 3
        db.close()

    @pytest.mark.asyncio
    async def test_handles_source_failure_gracefully(self):
        db = _make_db()
        good_job = Job(id="good-1", source="a", company="A", title="Good", description="D")
        good_source = MockSource(jobs=[good_job])
        failing_source = MockSource(fail=True)
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[failing_source, good_source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        apps = await scheduler.run_once()

        assert len(apps) == 1
        assert apps[0].job_id == "good-1"
        db.close()

    @pytest.mark.asyncio
    async def test_sets_last_run(self):
        db = _make_db()
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        assert scheduler.last_run is None
        await scheduler.run_once()
        assert scheduler.last_run is not None
        db.close()

    @pytest.mark.asyncio
    async def test_stores_job_in_database(self):
        db = _make_db()
        source = MockSource(jobs=[SAMPLE_JOB])
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[source],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        await scheduler.run_once()

        stored = db.get_job("sched-job-1")
        assert stored is not None
        assert stored.company == "Test Corp"
        db.close()


class TestSchedulerStop:
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        db = _make_db()
        evaluator = _make_evaluator()
        gen = _make_answer_gen()

        scheduler = Scheduler(
            sources=[],
            database=db,
            evaluator=evaluator,
            answer_generator=gen,
            profile=SAMPLE_PROFILE,
            config=_make_config(),
        )

        scheduler._running = True
        scheduler.stop()
        assert scheduler._running is False
        db.close()
