import logging

from pydantic import BaseModel

from src.llm.engine import LLMEngine
from src.models.application import Application
from src.models.job import Job
from src.profile.models import Profile
from src.storage.database import Database

logger = logging.getLogger("job-bot.review")


class ReviewDecision(BaseModel):
    approved: bool
    answers: dict[str, str]


class ReviewCancelledError(Exception):
    pass


class ReviewWorkflow:
    REWRITE_TEMPLATE = "rewrite"

    def __init__(
        self,
        database: Database,
        llm_engine: LLMEngine | None = None,
    ):
        self._db = database
        self._llm = llm_engine

    async def review_answers(
        self,
        application: Application,
        job: Job,
        answers: dict[str, str],
        profile: Profile | None = None,
    ) -> ReviewDecision:
        current = dict(answers)
        application.answers = current
        self._db.save_application(application)

        while True:
            self._show_review(job, current)
            action = self._prompt_action()

            if action == "approve":
                application.status = "approved"
                self._db.save_application(application)
                logger.info("Application %s approved", application.id)
                return ReviewDecision(approved=True, answers=current)

            if action == "cancel":
                application.status = "cancelled"
                self._db.save_application(application)
                logger.info("Application %s cancelled", application.id)
                return ReviewDecision(approved=False, answers=current)

            if action == "rewrite":
                current = await self._rewrite_all(current, job, profile)
                continue

            if action == "edit":
                current = self._edit_all(current)
                continue

    def _show_review(self, job: Job, answers: dict[str, str]) -> None:
        print(f"\n{'=' * 60}")
        print(f"Review: {job.title} at {job.company}")
        print(f"{'=' * 60}")
        for key, value in answers.items():
            print(f"\n--- {key} ---")
            print(value)

    def _prompt_action(self) -> str:
        print(f"\n{'=' * 60}")
        choice = input("[A]pprove, [E]dit, [R]ewrite, [C]ancel: ").strip().lower()
        print(f"{'=' * 60}\n")
        if choice in ("a", "approve"):
            return "approve"
        if choice in ("c", "cancel"):
            return "cancel"
        if choice in ("r", "rewrite"):
            return "rewrite"
        if choice in ("e", "edit"):
            return "edit"
        logger.warning("Unrecognised choice '%s', treating as cancel", choice)
        return "cancel"

    async def _rewrite_all(
        self,
        answers: dict[str, str],
        job: Job,
        profile: Profile | None = None,
    ) -> dict[str, str]:
        if self._llm is None:
            logger.warning("No LLM engine available for rewrite")
            return answers

        rewritten = dict(answers)
        name = profile.name if profile else "Applicant"
        skills = ", ".join(profile.skills) if profile and profile.skills else ""

        for key, text in answers.items():
            logger.info("Rewriting %s via LLM", key)
            variables = {
                "current_answer": text,
                "company": job.company,
                "title": job.title,
                "description": job.description,
                "name": name,
                "skills": skills,
            }
            new_text = await self._llm.generate_text(self.REWRITE_TEMPLATE, **variables)
            print(f"\n--- Rewritten {key} ---")
            print(new_text)

            choice = input("Keep this version? [Y]es, [N]o, [E]dit: ").strip().lower()
            if choice in ("y", "yes", ""):
                rewritten[key] = new_text
            elif choice in ("e", "edit"):
                rewritten[key] = input(f"Enter edited {key}: ").strip()
            else:
                print("Keeping original.")

        return rewritten

    def _edit_all(self, answers: dict[str, str]) -> dict[str, str]:
        edited = dict(answers)
        keys = list(edited.keys())

        print("\nWhich answer would you like to edit?")
        for i, key in enumerate(keys, 1):
            print(f"  {i}. {key}")
        choice = input(f"Enter number (1-{len(keys)}) or Enter to skip: ").strip()

        if not choice:
            return edited

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                key = keys[idx]
                print(f"\nCurrent {key}:")
                print(edited[key])
                new_value = input(f"\nNew {key}: ").strip()
                if new_value:
                    edited[key] = new_value
                    logger.info("User edited %s", key)
        except (ValueError, IndexError):
            logger.warning("Invalid edit selection: %s", choice)

        return edited
