import json
import logging
import re
from typing import Any

from src.llm.engine import LLMEngine
from src.models.job import Job
from src.profile.manager import ProfileManager
from src.profile.models import Profile

logger = logging.getLogger("job-bot.answer")


class AnswerGenerator:
    ANSWER_TEMPLATE = "answer_generation"
    SCREENER_TEMPLATE = "screener_answers"

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

    async def generate_for_fields(
        self,
        job: Job,
        fields: list[Any],
        profile: Profile | None = None,
    ) -> dict[str, str]:
        """Generate targeted answers for a list of form fields (e.g. screener questions).

        For standard fields (name, email, phone) a generic answer is returned.
        For custom textarea/text fields, each field's label is sent to the LLM
        as a question and a specific answer is generated.

        Args:
            job: The job being applied to.
            fields: Detected form fields with labels/questions.
            profile: The user's profile.

        Returns:
            Dict mapping field titles to generated answers.
        """
        if profile is None:
            profile = self._profile_manager.load_profile_from_resume(
                self._get_resume_path()
            )

        answers: dict[str, str] = {}
        text_fields: list[str] = []

        for field in fields:
            title = getattr(field, "title", "") or ""
            if title.strip():
                text_fields.append(title.strip())

        if not text_fields:
            return answers

        questions_text = "\n".join(f"- {q}" for q in text_fields)
        variables = self._build_variables(job, profile)
        variables["questions"] = questions_text

        try:
            raw = await self._llm.generate_text(self.SCREENER_TEMPLATE, **variables)
            parsed = self._parse_json_from_text(raw)
            if isinstance(parsed, dict):
                for question, answer in parsed.items():
                    if answer and isinstance(answer, str):
                        answers[question.strip()] = answer.strip()
                logger.info(
                    "Generated %d field-specific answers", len(answers)
                )
        except Exception:
            logger.exception("Error generating field answers")

        return answers

    @staticmethod
    def _parse_json_from_text(text: str) -> dict[str, Any] | None:
        """Extract and parse JSON object from LLM response text."""
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```\s*$", "", text)

        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        end = start
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if depth != 0:
            return None

        return json.loads(text[start:end])

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
