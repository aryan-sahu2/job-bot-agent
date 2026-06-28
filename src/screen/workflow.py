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
from src.screen.models import DetectedField, FieldType, ScreenJob, WorkflowState
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

        Flow:
        1. Scan screen for job description
        2. Detect form fields (early — form may already be visible)
        3. If fields found → generate per-field answers, skip apply click
        4. If no fields → generate generic answers, click apply, re-detect fields
        5. Fill fields
        6. Prompt user for decision
        7. Submit or review
        """
        try:
            self._state = WorkflowState.SCANNING
            logger.info("Starting screen workflow")

            await self._scan_screen()

            if not self._current_job or not self._current_job.description:
                logger.warning("No job description found on screen")
                self._state = WorkflowState.ERROR
                return False

            self._state = WorkflowState.DETECTING_FIELDS
            fields = self._form_detector.detect_fields()
            fields_count = len(fields)
            logger.info("Detected %d form field(s)", fields_count)

            self._state = WorkflowState.CLICKING_APPLY
            apply_clicked = False
            if fields_count > 0:
                logger.info("Form already visible, skipping apply click")
                apply_clicked = True
            else:
                apply_clicked = self._click_apply_button()
                if apply_clicked:
                    time.sleep(1.5)
                    fields = self._form_detector.detect_fields()
                    fields_count = len(fields)
                    logger.info("After apply: detected %d field(s)", fields_count)
                else:
                    logger.warning("No apply button found - user may need to click manually")

            self._state = WorkflowState.GENERATING_ANSWERS
            answers = await self._generate_answers(fields=fields)

            self._state = WorkflowState.FILLING_FIELDS
            success = 0
            fail = 0
            if fields and answers:
                success, fail = self._form_filler.fill_all_fields(fields, answers)
                logger.info("Filled %d fields, %d failed", success, fail)

            self._state = WorkflowState.AWAITING_DECISION
            should_submit = await self._prompt_user_decision(
                apply_clicked=apply_clicked,
                fields_count=fields_count,
                fields_filled=success,
                fields_failed=fail,
            )

            if should_submit:
                self._state = WorkflowState.SUBMITTING
                clicked = self._click_submit_button()
                if clicked:
                    await self._save_application("submitted")
                    logger.info("Application submitted successfully")
                else:
                    logger.warning(
                        "Could not find submit button. The form has been filled "
                        "but may need manual submission."
                    )
                    print(
                        "\nWarning: Could not find the submit button automatically.\n"
                        "The form fields have been filled. Please click Submit manually."
                    )
                    await self._save_application("reviewing")
            else:
                await self._save_application("reviewing")

            self._state = WorkflowState.COMPLETE
            current_state = self._state
            self._purge_context()
            return current_state == WorkflowState.COMPLETE

        except Exception:
            logger.exception("Error in screen workflow")
            self._state = WorkflowState.ERROR
            self._purge_context()
            return False

    async def _scan_screen(self) -> None:
        """Scan the current screen to extract job information."""
        logger.info("Scanning current screen for job information")
        self._current_job = self._parser.parse()

    async def _generate_answers(
        self, fields: list[DetectedField] | None = None
    ) -> dict[str, str]:
        """Generate personalized answers for the detected job and form fields.

        Detects whether the page has custom screener questions (e.g. Indeed)
        and generates per-field answers, or falls back to a generic cover letter
        for traditional application forms.

        Args:
            fields: Detected form fields. If empty, generates a generic cover letter.

        Returns:
            Dict mapping field identifiers/labels to generated values.
        """
        if not self._current_job or not self._profile:
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
        answers: dict[str, str] = {}

        # Always include profile identity fields
        if profile:
            if profile.name:
                parts = profile.name.split()
                answers["first_name"] = parts[0]
                answers["last_name"] = parts[-1] if len(parts) > 1 else ""
            answers["email"] = profile.email or ""
            answers["phone"] = profile.phone or ""
            answers["company"] = self._current_job.company or ""
            answers["position"] = self._current_job.title or ""

        # Check if there are custom textarea/text fields (screener questions)
        custom_fields = [
            f for f in (fields or [])
            if f.field_type in (FieldType.TEXTAREA, FieldType.TEXT)
            and f.title.strip()
        ]

        if custom_fields:
            logger.info("Generating per-field answers for %d custom field(s)", len(custom_fields))
            try:
                per_field = await self._answer_generator.generate_for_fields(
                    job=job, fields=custom_fields, profile=profile,
                )
                if per_field:
                    answers.update(per_field)
                    logger.info(
                        "Generated %d field-specific answers", len(per_field)
                    )
            except Exception:
                logger.exception("Error generating per-field answers")

        try:
            answer_text = await self._answer_generator.generate(
                job=job, profile=profile,
            )
            answers["cover_letter"] = answer_text
            answers["why_company"] = answer_text
        except Exception:
            logger.exception("Error generating cover letter")

        return answers

    def _click_apply_button(self) -> bool:
        """Find and click the apply button."""
        return self._button_finder.find_and_click_apply()

    def _click_submit_button(self) -> bool:
        """Click the submit button after filling fields.

        Uses find_and_click_submit which searches with SUBMIT_KEYWORDS
        (submit, send, next, continue, etc.) and falls back to OCR.
        """
        return self._button_finder.find_and_click_submit()

    async def _prompt_user_decision(
        self,
        apply_clicked: bool = False,
        fields_count: int = 0,
        fields_filled: int = 0,
        fields_failed: int = 0,
    ) -> bool:
        """Prompt the user to decide whether to submit or review.

        Args:
            apply_clicked: Whether the apply button was successfully clicked.
            fields_count: Total number of form fields detected.
            fields_filled: Number of fields filled successfully.
            fields_failed: Number of fields that failed to fill.

        Returns:
            True if user wants to auto-submit, False for manual review.
        """
        if not self._config.screen.ask_before_submit:
            return True

        print("\n" + "=" * 60)
        print("APPLICATION STATUS")
        print("=" * 60)

        if self._current_job:
            print(f"Job: {self._current_job.title}")
            print(f"Company: {self._current_job.company}")
            print(f"Location: {self._current_job.location}")

        print(f"\nApply button clicked: {'Yes' if apply_clicked else 'No'}")
        print(f"Form fields detected: {fields_count}")
        print(f"Fields filled: {fields_filled}")
        if fields_failed:
            print(f"Fields failed: {fields_failed}")

        if apply_clicked and fields_filled > 0:
            print("\nThe form has been filled with your profile data.")
        elif not apply_clicked and fields_count == 0:
            print(
                "\nNo apply button was found and no form fields were detected.\n"
                "You may need to click the apply/continue button manually in your browser."
            )
        else:
            print(
                "\nThe form fields have been partially processed."
            )

        print("\nOptions:")
        print("  [S] Submit automatically")
        print("  [R] Review manually (you click Submit)")
        print("  [C] Cancel and purge context")

        while True:
            choice = input("\nYour choice (S/R/C): ").strip().lower()

            if choice in ("s", "submit"):
                return True
            elif choice in ("r", "review", "manual"):
                print("\nPlease review the form in your browser and click Submit manually.")
                input("Press Enter after you've submitted or to continue...")
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
