import logging

from src.llm.engine import LLMEngine
from src.models.job import Job
from src.profile.manager import ProfileManager
from src.profile.models import Profile

logger = logging.getLogger("job-bot.answer")


class AnswerGenerator:
    ANSWER_TEMPLATE = "answer_generation"

    def __init__(
        self,
        llm_engine: LLMEngine,
        profile_manager: ProfileManager,
    ):
        self._llm = llm_engine
        self._profile_manager = profile_manager

    async def generate(
        self,
        job: Job,
        profile: Profile | None = None,
    ) -> str:
        if profile is None:
            profile = self._profile_manager.load_profile_from_resume(
                self._get_resume_path()
            )

        variables = self._build_variables(job, profile)
        answer = await self._llm.generate_text(
            self.ANSWER_TEMPLATE,
            **variables,
        )

        logger.info(
            "Generated answer for %s at %s (%d chars)",
            job.title,
            job.company,
            len(answer),
        )
        return answer

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
            "description": job.description,
            "name": profile.name,
            "profile_title": profile.title or "Not specified",
            "skills": ", ".join(profile.skills) if profile.skills else "Not specified",
            "experience": experience_str or "Not specified",
            "education": education_str or "Not specified",
            "summary": profile.summary or "Not specified",
        }
