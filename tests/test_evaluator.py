from unittest.mock import patch

import pytest

from src.evaluator.evaluator import JobEvaluator
from src.llm.base import LLMProvider
from src.llm.engine import LLMEngine, LLMEngineError
from src.models.evaluation import Evaluation
from src.models.job import Job
from src.profile.manager import ProfileManager
from src.profile.models import Education, Experience, Profile
from src.prompts.loader import PromptLoader


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.call_count = 0
        self._responses = responses or [
            '{"match_score": 85, "strengths": ["Good fit"], '
            '"missing_skills": ["AWS"], "summary": "Strong match."}',
        ]

    async def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count <= len(self._responses):
            return self._responses[self.call_count - 1]
        return self._responses[-1]


SAMPLE_JOB = Job(
    id="job-1",
    source="wellfound",
    company="Tech Corp",
    title="Senior Engineer",
    location="Remote",
    employment_type="full-time",
    description="We need a senior engineer.",
    skills=["Python", "Go"],
)

SAMPLE_PROFILE = Profile(
    name="Jane Doe",
    title="Senior Software Engineer",
    skills=["Python", "Go", "Kubernetes"],
    experience=[
        Experience(
            title="Senior Engineer",
            company="Startup Inc",
            start_date="2020-01",
            end_date="Present",
        ),
    ],
    education=[
        Education(
            degree="BS",
            institution="MIT",
            field="CS",
            graduation_year="2016",
        ),
    ],
)


class TestEvaluationModel:
    def test_create_evaluation(self):
        ev = Evaluation(
            job_id="j1",
            match_score=85,
            strengths=["Good fit"],
            missing_skills=["AWS"],
            summary="Strong match.",
        )
        assert ev.job_id == "j1"
        assert ev.match_score == 85
        assert ev.strengths == ["Good fit"]
        assert ev.missing_skills == ["AWS"]
        assert ev.summary == "Strong match."
        assert ev.evaluated_at is not None

    def test_evaluation_default_evaluated_at(self):
        ev = Evaluation(
            job_id="j1",
            match_score=0,
            strengths=[],
            missing_skills=[],
            summary="",
        )
        assert ev.evaluated_at is not None


class TestJobEvaluator:
    @pytest.mark.asyncio
    async def test_evaluate_returns_evaluation(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        manager = ProfileManager()
        evaluator = JobEvaluator(engine, manager)

        result = await evaluator.evaluate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert isinstance(result, Evaluation)
        assert result.job_id == "job-1"
        assert result.match_score == 85
        assert result.strengths == ["Good fit"]
        assert result.missing_skills == ["AWS"]
        assert result.summary == "Strong match."

    @pytest.mark.asyncio
    async def test_evaluate_calls_llm_with_correct_template(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        evaluator = JobEvaluator(engine, ProfileManager())

        await evaluator.evaluate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_evaluate_without_profile_loads_from_manager(self, tmp_path):
        resume_file = tmp_path / "resume.txt"
        resume_file.write_text("Jane Doe\njane@example.com\nSkills: Python")

        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        manager = ProfileManager()
        evaluator = JobEvaluator(engine, manager)

        with patch("src.config.loader.ConfigLoader") as mock_config_loader:
            mock_config_loader.return_value.load.return_value = {
                "resume": {"path": str(resume_file)},
            }
            result = await evaluator.evaluate(SAMPLE_JOB)

        assert isinstance(result, Evaluation)
        assert result.job_id == "job-1"

    @pytest.mark.asyncio
    async def test_evaluate_raises_on_llm_failure(self):
        provider = MockProvider(["bad json", "also bad", "still bad"])
        engine = LLMEngine(provider, PromptLoader(), max_retries=2)
        evaluator = JobEvaluator(engine, ProfileManager())

        with pytest.raises(LLMEngineError, match="Evaluation"):
            await evaluator.evaluate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert provider.call_count == 3

    @pytest.mark.asyncio
    async def test_build_variables_includes_all_fields(self):
        variables = JobEvaluator._build_variables(SAMPLE_JOB, SAMPLE_PROFILE)

        assert variables["company"] == "Tech Corp"
        assert variables["title"] == "Senior Engineer"
        assert variables["location"] == "Remote"
        assert variables["employment_type"] == "full-time"
        assert variables["description"] == "We need a senior engineer."
        assert variables["name"] == "Jane Doe"
        assert variables["profile_title"] == "Senior Software Engineer"
        assert "Python" in variables["skills"]
        assert "Startup Inc" in variables["experience"]
        assert "MIT" in variables["education"]

    def test_build_variables_empty_profile(self):
        empty_profile = Profile(name="No One")
        job = Job(id="j1", source="test", company="C", title="T", description="D")
        variables = JobEvaluator._build_variables(job, empty_profile)

        assert variables["company"] == "C"
        assert variables["profile_title"] == "Not specified"
        assert variables["skills"] == "Not specified"
        assert variables["experience"] == "Not specified"
        assert variables["education"] == "Not specified"

    @pytest.mark.asyncio
    async def test_evaluate_does_not_mutate_job(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        evaluator = JobEvaluator(engine, ProfileManager())

        original_id = SAMPLE_JOB.id
        original_company = SAMPLE_JOB.company

        await evaluator.evaluate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert SAMPLE_JOB.id == original_id
        assert SAMPLE_JOB.company == original_company
