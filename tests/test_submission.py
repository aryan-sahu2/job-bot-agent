from unittest.mock import AsyncMock

import pytest

from src.models.application import Application
from src.models.forms import FormField
from src.models.job import Job
from src.storage.database import Database
from src.workflow.submitter import SubmissionError, Submitter

SAMPLE_JOB = Job(
    id="job-1",
    source="wellfound",
    company="Tech Corp",
    title="Senior Engineer",
    description="We need a senior engineer.",
    apply_url="https://example.com/apply",
)

SAMPLE_FORM_FIELDS = [
    FormField(selector="#name", field_type="text", value="Jane Doe"),
    FormField(selector="#submit", field_type="text", value="I am a great fit."),
]

SUBMIT_SELECTOR = "#submit-button"


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    database.initialize()
    return database


@pytest.fixture
def approved_app() -> Application:
    return Application(id="app-1", job_id="job-1", status="approved")


@pytest.fixture
def mock_browser() -> AsyncMock:
    browser = AsyncMock()
    browser.navigate = AsyncMock()
    browser.click = AsyncMock()
    return browser


@pytest.fixture
def mock_form_filler() -> AsyncMock:
    ff = AsyncMock()
    ff.fill_fields = AsyncMock()
    return ff


class TestSubmitter:
    @pytest.mark.asyncio
    async def test_submit_happy_path(
        self,
        db: Database,
        approved_app: Application,
        mock_browser: AsyncMock,
        mock_form_filler: AsyncMock,
    ):
        db.save_application(approved_app)
        submitter = Submitter(db, mock_browser, mock_form_filler)

        await submitter.submit(approved_app, SAMPLE_JOB, SAMPLE_FORM_FIELDS, SUBMIT_SELECTOR)

        mock_browser.navigate.assert_awaited_once_with(SAMPLE_JOB.apply_url)
        mock_form_filler.fill_fields.assert_awaited_once_with(SAMPLE_FORM_FIELDS)
        mock_browser.click.assert_awaited_once_with(SUBMIT_SELECTOR)

    @pytest.mark.asyncio
    async def test_submit_updates_status_in_db(
        self,
        db: Database,
        approved_app: Application,
        mock_browser: AsyncMock,
        mock_form_filler: AsyncMock,
    ):
        db.save_application(approved_app)
        submitter = Submitter(db, mock_browser, mock_form_filler)

        await submitter.submit(approved_app, SAMPLE_JOB, SAMPLE_FORM_FIELDS, SUBMIT_SELECTOR)

        retrieved = db.get_application(approved_app.id)
        assert retrieved is not None
        assert retrieved.status == "submitted"
        assert retrieved.submitted_at is not None

    @pytest.mark.asyncio
    async def test_submit_rejects_non_approved_status(
        self,
        db: Database,
        mock_browser: AsyncMock,
        mock_form_filler: AsyncMock,
    ):
        draft_app = Application(id="app-2", job_id="job-1", status="draft")
        submitter = Submitter(db, mock_browser, mock_form_filler)

        with pytest.raises(SubmissionError, match="status is 'draft'"):
            await submitter.submit(draft_app, SAMPLE_JOB, SAMPLE_FORM_FIELDS, SUBMIT_SELECTOR)

        mock_browser.navigate.assert_not_called()
        mock_browser.click.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_rejects_missing_apply_url(
        self,
        db: Database,
        approved_app: Application,
        mock_browser: AsyncMock,
        mock_form_filler: AsyncMock,
    ):
        job_no_url = Job(
            id="job-2",
            source="wellfound",
            company="No URL Corp",
            title="Engineer",
            description="No apply URL.",
            apply_url=None,
        )
        submitter = Submitter(db, mock_browser, mock_form_filler)

        with pytest.raises(SubmissionError, match="no apply URL"):
            await submitter.submit(approved_app, job_no_url, SAMPLE_FORM_FIELDS, SUBMIT_SELECTOR)

        mock_browser.navigate.assert_not_called()
        mock_browser.click.assert_not_called()
