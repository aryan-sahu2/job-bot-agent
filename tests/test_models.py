from src.models.application import Application
from src.models.job import Job


class TestJob:
    def test_create_job_minimal(self):
        job = Job(
            id="test-1",
            source="wellfound",
            company="Test Corp",
            title="Software Engineer",
            description="A test job description",
        )
        assert job.id == "test-1"
        assert job.source == "wellfound"
        assert job.skills == []
        assert job.metadata == {}

    def test_create_job_with_all_fields(self):
        job = Job(
            id="test-2",
            source="wellfound",
            company="Test Corp",
            title="Senior Engineer",
            location="San Francisco",
            employment_type="full-time",
            salary="$150k-$200k",
            description="A senior role",
            skills=["Python", "Go"],
            apply_url="https://example.com/apply",
        )
        assert job.location == "San Francisco"
        assert job.employment_type == "full-time"
        assert job.salary == "$150k-$200k"


class TestApplication:
    def test_create_application_defaults(self):
        app = Application(id="app-1", job_id="job-1")
        assert app.status == "draft"
        assert app.answers is None
        assert app.submitted_at is None

    def test_create_application_submitted(self):
        app = Application(id="app-2", job_id="job-2", status="submitted")
        assert app.status == "submitted"
