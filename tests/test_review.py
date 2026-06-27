from unittest.mock import AsyncMock, patch

import pytest

from src.models.application import Application
from src.models.job import Job
from src.storage.database import Database
from src.workflow.review import ReviewDecision, ReviewWorkflow

SAMPLE_JOB = Job(
    id="job-1",
    source="wellfound",
    company="Tech Corp",
    title="Senior Engineer",
    description="We need a senior engineer.",
)

SAMPLE_ANSWERS = {"cover_letter": "I am a great fit for this role."}


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    database.initialize()
    return database


@pytest.fixture
def app() -> Application:
    return Application(id="app-1", job_id="job-1")


class TestReviewApprove:
    @pytest.mark.asyncio
    async def test_approve_returns_approved_true(self, db: Database, app: Application):
        inputs = iter(["a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is True
        assert result.answers == SAMPLE_ANSWERS

    @pytest.mark.asyncio
    async def test_approve_updates_status_in_db(self, db: Database, app: Application):
        db.save_application(app)
        inputs = iter(["a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        retrieved = db.get_application(app.id)
        assert retrieved is not None
        assert retrieved.status == "approved"

    @pytest.mark.asyncio
    async def test_approve_saves_answers_in_db(self, db: Database, app: Application):
        db.save_application(app)
        inputs = iter(["a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        retrieved = db.get_application(app.id)
        assert retrieved is not None
        assert retrieved.answers == SAMPLE_ANSWERS


class TestReviewCancel:
    @pytest.mark.asyncio
    async def test_cancel_returns_approved_false(self, db: Database, app: Application):
        inputs = iter(["c"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is False

    @pytest.mark.asyncio
    async def test_cancel_updates_status_in_db(self, db: Database, app: Application):
        db.save_application(app)
        inputs = iter(["c"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        retrieved = db.get_application(app.id)
        assert retrieved is not None
        assert retrieved.status == "cancelled"

    @pytest.mark.asyncio
    async def test_unrecognised_input_falls_back_to_cancel(
        self, db: Database, app: Application
    ):
        db.save_application(app)
        inputs = iter(["x"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is False
        retrieved = db.get_application(app.id)
        assert retrieved.status == "cancelled"


class TestReviewRewrite:
    @pytest.mark.asyncio
    async def test_rewrite_calls_llm_and_keeps_new_version(
        self, db: Database, app: Application
    ):
        mock_llm = AsyncMock()
        mock_llm.generate_text = AsyncMock(
            return_value="Rewritten cover letter text."
        )

        inputs = iter(["r", "y", "a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db, llm_engine=mock_llm)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        mock_llm.generate_text.assert_awaited_once()
        assert result.approved is True
        assert result.answers["cover_letter"] == "Rewritten cover letter text."

    @pytest.mark.asyncio
    async def test_rewrite_skipped_when_no_llm(
        self, db: Database, app: Application
    ):
        inputs = iter(["r", "a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db, llm_engine=None)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is True
        assert result.answers == SAMPLE_ANSWERS

    @pytest.mark.asyncio
    async def test_rewrite_reject_keeps_original(
        self, db: Database, app: Application
    ):
        mock_llm = AsyncMock()
        mock_llm.generate_text = AsyncMock(
            return_value="Rewritten version."
        )

        inputs = iter(["r", "n", "a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db, llm_engine=mock_llm)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is True
        assert result.answers["cover_letter"] == "I am a great fit for this role."


class TestReviewEdit:
    @pytest.mark.asyncio
    async def test_edit_changes_answer_text(
        self, db: Database, app: Application
    ):
        inputs = iter(["e", "1", "I am an excellent fit.", "a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is True
        assert result.answers["cover_letter"] == "I am an excellent fit."

    @pytest.mark.asyncio
    async def test_edit_skip_keeps_original(
        self, db: Database, app: Application
    ):
        inputs = iter(["e", "", "a"])
        with patch("builtins.input", lambda _: next(inputs)):
            workflow = ReviewWorkflow(db)
            result = await workflow.review_answers(app, SAMPLE_JOB, SAMPLE_ANSWERS)

        assert result.approved is True
        assert result.answers["cover_letter"] == "I am a great fit for this role."


class TestReviewDecisionModel:
    def test_review_decision_approved(self):
        decision = ReviewDecision(
            approved=True,
            answers={"cover_letter": "Hello"},
        )
        assert decision.approved is True
        assert decision.answers["cover_letter"] == "Hello"

    def test_review_decision_cancelled(self):
        decision = ReviewDecision(
            approved=False,
            answers={"cover_letter": "Hello"},
        )
        assert decision.approved is False
