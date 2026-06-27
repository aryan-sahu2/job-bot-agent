import logging

from pydantic import BaseModel

from src.llm.engine import LLMEngine
from src.models.evaluation import Evaluation
from src.models.job import Job
from src.profile.manager import ProfileManager
from src.profile.models import Profile

logger = logging.getLogger("job-bot.evaluator")


class _EvaluationResult(BaseModel):
    match_score: int
    strengths: list[str]
    missing_skills: list[str]
    summary: str


class JobEvaluator:
    MATCH_TEMPLATE = "job_matching"

    def __init__(
        self,
        llm_engine: LLMEngine,
        profile_manager: ProfileManager,
    ):
        self._llm = llm_engine
        self._profile_manager = profile_manager

    async def evaluate(
        self,
        job: Job,
        profile: Profile | None = None,
    ) -> Evaluation:
        if profile is None:
            profile = self._profile_manager.load_profile_from_resume(
                self._get_resume_path()
            )

        variables = self._build_variables(job, profile)
        raw = await self._llm.generate_structured(
            self.MATCH_TEMPLATE,
            _EvaluationResult,
            **variables,
        )

        return Evaluation(
            job_id=job.id,
            match_score=raw.match_score,
            strengths=raw.strengths,
            missing_skills=raw.missing_skills,
            summary=raw.summary,
        )

    def _get_resume_path(self) -> str:
        from src.config.loader import ConfigLoader

        config = ConfigLoader().load()
        path = config.get("resume", {}).get("path", "resume.txt")
        return path

    @staticmethod
    def _build_variables(job: Job, profile: Profile) -> dict[str, str]:
        experience_str = "; ".join(
            f"{e.title} at {e.company} ({e.start_date} - {e.end_date or 'Present'})"
            for e in profile.experience
        )
        education_str = "; ".join(
            f"{e.degree} in {e.field or ''} at {e.institution}"
            for e in profile.education
        )
        return {
            "company": job.company,
            "title": job.title,
            "location": job.location or "Not specified",
            "employment_type": job.employment_type or "Not specified",
            "description": job.description,
            "name": profile.name,
            "profile_title": profile.title or "Not specified",
            "skills": ", ".join(profile.skills) if profile.skills else "Not specified",
            "experience": experience_str or "Not specified",
            "education": education_str or "Not specified",
        }
