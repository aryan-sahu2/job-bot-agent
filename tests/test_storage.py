from datetime import datetime

import pytest

from src.models.application import Application
from src.models.job import Job
from src.storage.database import Database


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    database.initialize()
    return database


class TestDatabaseJobs:
    def test_save_and_get_job(self, db: Database):
        job = Job(
            id="job-1",
            source="wellfound",
            company="Test Corp",
            title="Software Engineer",
            description="A great role",
        )
        db.save_job(job)
        retrieved = db.get_job("job-1")
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.company == job.company
        assert retrieved.title == job.title
        assert retrieved.skills == []
        assert retrieved.metadata == {}

    def test_save_and_get_job_with_all_fields(self, db: Database):
        job = Job(
            id="job-2",
            source="wellfound",
            company="Startup Inc",
            title="Senior Engineer",
            location="Remote",
            employment_type="full-time",
            salary="$200k",
            description="Senior role",
            skills=["Python", "Go"],
            apply_url="https://example.com/apply",
            posted_date=datetime(2026, 1, 15),
            metadata={"source_id": "123"},
        )
        db.save_job(job)
        retrieved = db.get_job("job-2")
        assert retrieved is not None
        assert retrieved.location == "Remote"
        assert retrieved.employment_type == "full-time"
        assert retrieved.salary == "$200k"
        assert retrieved.skills == ["Python", "Go"]
        assert retrieved.apply_url == "https://example.com/apply"
        assert retrieved.posted_date == datetime(2026, 1, 15)
        assert retrieved.metadata == {"source_id": "123"}

    def test_get_nonexistent_job(self, db: Database):
        assert db.get_job("nonexistent") is None

    def test_list_jobs_empty(self, db: Database):
        assert db.list_jobs() == []

    def test_list_jobs(self, db: Database):
        job1 = Job(id="j1", source="wellfound", company="A", title="T1", description="D1")
        job2 = Job(id="j2", source="wellfound", company="B", title="T2", description="D2")
        db.save_job(job1)
        db.save_job(job2)
        jobs = db.list_jobs()
        assert len(jobs) == 2

    def test_save_job_replaces_existing(self, db: Database):
        job = Job(id="j1", source="wf", company="A", title="T1", description="D1")
        db.save_job(job)
        updated = Job(id="j1", source="wf", company="B", title="T2", description="D2")
        db.save_job(updated)
        assert db.list_jobs() == [updated]


class TestDatabaseApplications:
    def test_save_and_get_application(self, db: Database):
        app = Application(id="app-1", job_id="job-1")
        db.save_application(app)
        retrieved = db.get_application("app-1")
        assert retrieved is not None
        assert retrieved.id == "app-1"
        assert retrieved.job_id == "job-1"
        assert retrieved.status == "draft"
        assert retrieved.answers is None

    def test_save_and_get_application_with_answers(self, db: Database):
        app = Application(
            id="app-2",
            job_id="job-2",
            status="draft",
            answers={"cover_letter": "I am a great fit."},
        )
        db.save_application(app)
        retrieved = db.get_application("app-2")
        assert retrieved is not None
        assert retrieved.answers == {"cover_letter": "I am a great fit."}

    def test_get_nonexistent_application(self, db: Database):
        assert db.get_application("nonexistent") is None

    def test_list_applications_empty(self, db: Database):
        assert db.list_applications() == []

    def test_list_applications(self, db: Database):
        app1 = Application(id="a1", job_id="j1")
        app2 = Application(id="a2", job_id="j2")
        db.save_application(app1)
        db.save_application(app2)
        apps = db.list_applications()
        assert len(apps) == 2

    def test_update_application_status(self, db: Database):
        app = Application(id="app-1", job_id="job-1")
        db.save_application(app)
        db.update_application_status("app-1", "submitted")
        retrieved = db.get_application("app-1")
        assert retrieved is not None
        assert retrieved.status == "submitted"

    def test_save_application_replaces_existing(self, db: Database):
        app = Application(id="a1", job_id="j1", status="draft")
        db.save_application(app)
        updated = Application(id="a1", job_id="j1", status="submitted")
        db.save_application(updated)
        retrieved = db.get_application("a1")
        assert retrieved is not None
        assert retrieved.status == "submitted"


class TestDatabaseEdgeCases:
    def test_initialize_twice_is_idempotent(self, db: Database):
        db.initialize()
        db.initialize()
        job = Job(id="j1", source="wf", company="C", title="T", description="D")
        db.save_job(job)
        assert db.get_job("j1") is not None

    def test_save_job_with_null_optionals(self, db: Database):
        job = Job(
            id="j1",
            source="wf",
            company="C",
            title="T",
            description="D",
            location=None,
            employment_type=None,
            salary=None,
            apply_url=None,
            posted_date=None,
        )
        db.save_job(job)
        retrieved = db.get_job("j1")
        assert retrieved is not None
        assert retrieved.location is None
        assert retrieved.employment_type is None
        assert retrieved.salary is None
        assert retrieved.apply_url is None
        assert retrieved.posted_date is None

    def test_close_then_reconnect(self, tmp_path):
        db_path = tmp_path / "test.db"
        database = Database(db_path)
        database.initialize()
        job = Job(id="j1", source="wf", company="C", title="T", description="D")
        database.save_job(job)
        database.close()
        retrieved = database.get_job("j1")
        assert retrieved is not None
        assert retrieved.id == "j1"
