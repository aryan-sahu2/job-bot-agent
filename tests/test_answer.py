from unittest.mock import patch

import pytest

from src.llm.base import LLMProvider
from src.llm.engine import LLMEngine
from src.models.job import Job
from src.profile.manager import ProfileManager
from src.profile.models import Education, Experience, Profile
from src.prompts.loader import PromptLoader
from src.workflow.answer import AnswerGenerator


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.call_count = 0
        self._responses = responses or [
            "I am excited to apply for this role. My experience in Python "
            "and distributed systems makes me a strong fit.",
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
    description="We need a senior engineer with Python and Go experience.",
    skills=["Python", "Go"],
)

SAMPLE_PROFILE = Profile(
    name="Jane Doe",
    title="Senior Software Engineer",
    skills=["Python", "Go", "Kubernetes"],
    summary="Experienced backend engineer with 8 years in distributed systems.",
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


class TestAnswerGenerator:
    @pytest.mark.asyncio
    async def test_generate_returns_string(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        manager = ProfileManager()
        generator = AnswerGenerator(engine, manager)

        result = await generator.generate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_calls_llm_with_correct_template(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        generator = AnswerGenerator(engine, ProfileManager())

        await generator.generate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_without_profile_loads_from_manager(self, tmp_path):
        resume_file = tmp_path / "resume.txt"
        resume_file.write_text("Jane Doe\njane@example.com\nSkills: Python")

        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        manager = ProfileManager()
        generator = AnswerGenerator(engine, manager)

        with patch("src.config.loader.ConfigLoader") as mock_config_loader:
            mock_config_loader.return_value.load.return_value = {
                "resume": {"path": str(resume_file)},
            }
            result = await generator.generate(SAMPLE_JOB)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_variables_includes_all_fields(self):
        variables = AnswerGenerator._build_variables(SAMPLE_JOB, SAMPLE_PROFILE)

        assert variables["company"] == "Tech Corp"
        assert variables["title"] == "Senior Engineer"
        assert (
            variables["description"]
            == "We need a senior engineer with Python and Go experience."
        )
        assert variables["name"] == "Jane Doe"
        assert variables["profile_title"] == "Senior Software Engineer"
        assert "Python" in variables["skills"]
        assert "Startup Inc" in variables["experience"]
        assert "MIT" in variables["education"]
        assert "distributed systems" in variables["summary"]

    def test_build_variables_empty_profile(self):
        empty_profile = Profile(name="No One")
        job = Job(id="j1", source="test", company="C", title="T", description="D")
        variables = AnswerGenerator._build_variables(job, empty_profile)

        assert variables["company"] == "C"
        assert variables["profile_title"] == "Not specified"
        assert variables["skills"] == "Not specified"
        assert variables["experience"] == "Not specified"
        assert variables["education"] == "Not specified"
        assert variables["summary"] == "Not specified"

    @pytest.mark.asyncio
    async def test_generate_does_not_mutate_job(self):
        provider = MockProvider()
        engine = LLMEngine(provider, PromptLoader())
        generator = AnswerGenerator(engine, ProfileManager())

        original_id = SAMPLE_JOB.id
        original_company = SAMPLE_JOB.company

        await generator.generate(SAMPLE_JOB, profile=SAMPLE_PROFILE)

        assert SAMPLE_JOB.id == original_id
        assert SAMPLE_JOB.company == original_company
