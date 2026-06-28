"""Screen-aware workflow orchestrator."""

from __future__ import annotations

import logging
import time
from typing import Any

from src.config.loader import Config
from src.llm.engine import LLMEngine
from src.profile.manager import ProfileManager
from src.screen.button_finder import ApplyButtonFinder
from src.screen.form_detector import FormDetector
from src.screen.form_filler import FormFiller
from src.screen.models import ScreenJob, WorkflowState
from src.screen.parser import JobDescriptionParser
from src.screen.reader import ScreenReader
from src.storage.database import Database
from src.workflow.answer import AnswerGenerator

logger = logging.getLogger(__name__)


class ScreenWorkflow:
    """Orchestrates the screen-aware job application workflow.

    Flow:
    1. User presses hotkey while viewing a job posting
    2. App reads the screen and parses the job description
    3. App generates personalized answers via LLM
    4. App finds and clicks the Apply button
    5. App detects form fields
    6. App fills fields with profile data + AI answers
    7. User decides to review or auto-submit
    8. Context is purged after completion
    """

    def __init__(self, config: Config) -> None:
        """Initialize the screen workflow.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._state = WorkflowState.IDLE
        self._current_job: ScreenJob | None = None
        self._current_context: dict[str, Any] = {}

        self._reader = ScreenReader()
        self._parser = JobDescriptionParser(self._reader)
        self._button_finder = ApplyButtonFinder(self._reader)
        self._form_detector = FormDetector(self._reader)
        self._form_filler = FormFiller(self._reader, self._form_detector)

        self._profile_manager: ProfileManager | None = None
        self._profile: Any = None
        self._llm_engine: LLMEngine | None = None
        self._answer_generator: AnswerGenerator | None = None
        self._database: Database | None = None

    def initialize(
        self,
        profile_manager: ProfileManager,
        profile: Any,
        llm_engine: LLMEngine,
        answer_generator: AnswerGenerator,
        database: Database,
    ) -> None:
        """Initialize reusable components.

        Must be called before running the workflow.
        """
        self._profile_manager = profile_manager
        self._profile = profile
        self._llm_engine = llm_engine
        self._answer_generator = answer_generator
        self._database = database
        logger.info("ScreenWorkflow initialized")

    @property
    def state(self) -> WorkflowState:
        """Get the current workflow state."""
        return self._state

    @property
    def current_job(self) -> ScreenJob | None:
        """Get the currently processed job."""
        return self._current_job

    async def run_once(self) -> bool:
        """Run the workflow once on the current screen.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        try:
            self._state = WorkflowState.SCANNING
            logger.info("Starting screen workflow")

            await self._scan_screen()

            if not self._current_job or not self._current_job.description:
                logger.warning("No job description found on screen")
                self._state = WorkflowState.ERROR
                return False

            self._state = WorkflowState.READING_JOB
            logger.info(
                "Detected job: '%s' at '%s'",
                self._current_job.title,
                self._current_job.company,
            )

            self._state = WorkflowState.GENERATING_ANSWERS
            answers = await self._generate_answers()

            self._state = WorkflowState.CLICKING_APPLY
            if not self._click_apply_button():
                logger.warning("No apply button found - user may need to click manually")

            self._state = WorkflowState.DETECTING_FIELDS
            time.sleep(1)
            fields = self._form_detector.detect_fields()
            logger.info("Detected %d form fields", len(fields))

            self._state = WorkflowState.FILLING_FIELDS
            if fields and answers:
                success, fail = self._form_filler.fill_all_fields(fields, answers)
                logger.info("Filled %d fields, %d failed", success, fail)

            self._state = WorkflowState.AWAITING_DECISION
            should_submit = await self._prompt_user_decision()

            if should_submit:
                self._state = WorkflowState.SUBMITTING
                self._click_submit_button()
                await self._save_application("submitted")
            else:
                await self._save_application("reviewing")

            self._state = WorkflowState.COMPLETE
            self._purge_context()
            return True

        except Exception:
            logger.exception("Error in screen workflow")
            self._state = WorkflowState.ERROR
            self._purge_context()
            return False

    async def _scan_screen(self) -> None:
        """Scan the current screen to extract job information."""
        logger.info("Scanning current screen for job information")
        self._current_job = self._parser.parse()

    async def _generate_answers(self) -> dict[str, str]:
        """Generate personalized answers for the detected job."""
        if not self._current_job or not self._answer_generator or not self._profile:
            return {}

        from src.models.job import Job

        job = Job(
            id="screen_" + str(int(time.time())),
            source="screen",
            company=self._current_job.company,
            title=self._current_job.title,
            location=self._current_job.location,
            description=self._current_job.description,
        )

        profile = self._profile

        try:
            answer_text = await self._answer_generator.generate(
                job=job,
                profile=profile,
            )

            answers = {
                "cover_letter": answer_text,
                "why_company": answer_text,
            }

            if self._current_job.company:
                answers["company"] = self._current_job.company
            if self._current_job.title:
                answers["position"] = self._current_job.title

            if profile:
                answers["first_name"] = profile.name.split()[0] if profile.name else ""
                answers["last_name"] = profile.name.split()[-1] if profile.name else ""
                answers["email"] = profile.email or ""
                answers["phone"] = profile.phone or ""

            return answers
        except Exception:
            logger.exception("Error generating answers")
            return {}

    def _click_apply_button(self) -> bool:
        """Find and click the apply button."""
        return self._button_finder.find_and_click_apply()

    def _click_submit_button(self) -> bool:
        """Click the submit button after filling fields."""
        return self._button_finder.find_and_click_apply()

    async def _prompt_user_decision(self) -> bool:
        """Prompt the user to decide whether to submit or review.

        Returns:
            True if user wants to auto-submit, False for manual review.
        """
        if not self._config.screen.ask_before_submit:
            return True

        print("\n" + "=" * 60)
        print("APPLICATION READY FOR SUBMISSION")
        print("=" * 60)

        if self._current_job:
            print(f"Job: {self._current_job.title}")
            print(f"Company: {self._current_job.company}")
            print(f"Location: {self._current_job.location}")

        print("\nThe form has been filled with your profile data.")
        print("\nOptions:")
        print("  [S] Submit automatically")
        print("  [R] Review manually (you click Submit)")
        print("  [C] Cancel and purge context")

        while True:
            choice = input("\nYour choice (S/R/C): ").strip().lower()

            if choice in ("s", "submit"):
                return True
            elif choice in ("r", "review", "manual"):
                print("\nForm is filled. Please review and click Submit manually.")
                input("Press Enter after you've submitted...")
                return False
            elif choice in ("c", "cancel"):
                return False
            else:
                print("Invalid choice. Please enter S, R, or C.")

    async def _save_application(self, status: str) -> None:
        """Save the application to the database."""
        if not self._database or not self._current_job:
            return

        try:
            from uuid import uuid4

            from src.models.application import Application

            app = Application(
                id=str(uuid4()),
                job_id="screen_" + str(int(time.time())),
                status=status,
                answers=self._current_context.get("answers", {}),
            )
            self._database.save_application(app)
            logger.info("Saved application with status: %s", status)
        except Exception:
            logger.exception("Error saving application")

    def _purge_context(self) -> None:
        """Clear all context from memory."""
        self._current_job = None
        self._current_context.clear()
        self._state = WorkflowState.IDLE
        logger.info("Context purged")

    def get_status(self) -> dict[str, Any]:
        """Get the current workflow status."""
        return {
            "state": self._state.value,
            "current_job": self._current_job.model_dump() if self._current_job else None,
        }
