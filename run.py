import argparse
import asyncio
import logging

from src.browser.engine import BrowserEngine
from src.config.loader import ConfigLoader
from src.evaluator.evaluator import JobEvaluator
from src.llm.engine import LLMEngine
from src.llm.ollama import OllamaProvider
from src.profile.manager import ProfileManager
from src.prompts.loader import PromptLoader
from src.sources.base import Source
from src.sources.greenhouse import GreenhouseSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.wellfound import WellfoundSource
from src.storage.database import Database
from src.workflow.answer import AnswerGenerator

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("job-bot")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("job-bot")


def _build_sources(browser: BrowserEngine, config: object) -> list[Source]:
    sources: list[Source] = []
    sources.append(WellfoundSource(browser))

    if config.greenhouse.enabled and config.greenhouse.board_slugs:
        sources.append(GreenhouseSource(browser, config.greenhouse.board_slugs))

    if config.lever.enabled and config.lever.company_slugs:
        sources.append(LeverSource(browser, config.lever.company_slugs))

    if config.linkedin.enabled and config.linkedin.keywords:
        sources.append(
            LinkedInSource(browser, config.linkedin.keywords, config.linkedin.location)
        )

    return sources


async def _ensure_logins(browser: BrowserEngine, config: object) -> None:
    if config.linkedin.enabled:
        logged_in = await browser.pause_for_login(
            url="https://www.linkedin.com/login",
            login_indicator="input#session_key",
            logged_in_indicator="div.feed-identity-module, input#global-nav-search",
        )
        if logged_in:
            print("LinkedIn session ready.\n")


async def run_interactive(config: object) -> None:
    db = Database(config.storage.database)
    db.initialize()

    profile_mgr = ProfileManager()
    profile = profile_mgr.load_profile_from_resume("resume.txt")

    provider = OllamaProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
    )
    prompt_loader = PromptLoader()
    llm = LLMEngine(provider, prompt_loader)

    async with BrowserEngine(config.browser) as browser:
        await _ensure_logins(browser, config)

        sources = _build_sources(browser, config)
        jobs = []
        for source in sources:
            jobs.extend(await source.discover())

        if not jobs:
            print("No jobs discovered from any source.")
            print("Using a test job to demonstrate the pipeline.\n")
            from datetime import datetime

            from src.models.job import Job

            jobs = [
                Job(
                    id="test-job-1",
                    source="manual",
                    company="Acme Startup",
                    title="Senior Full-Stack Engineer",
                    description=(
                        "We are looking for a senior full-stack engineer with "
                        "experience in Python, TypeScript, React, and AWS to join "
                        "our growing team. You will build and maintain our core "
                        "platform serving 100k+ users."
                    ),
                    apply_url=None,
                    posted_date=datetime.now(),
                )
            ]

        evaluator = JobEvaluator(llm, profile_mgr)
        generator = AnswerGenerator(llm, profile_mgr)

        for job in jobs:
            db.save_job(job)

            evaluation = await evaluator.evaluate(job, profile)
            print(f"\n{'=' * 60}")
            print(f"{job.title} @ {job.company}")
            print(f"Match: {evaluation.match_score}/100")
            print(f"Strengths: {', '.join(evaluation.strengths)}")
            print(f"Missing: {', '.join(evaluation.missing_skills)}")
            print(f"Summary: {evaluation.summary}")

            answer = await generator.generate(job, profile)

            from uuid import uuid4

            from src.models.application import Application
            from src.workflow.review import ReviewWorkflow

            app = Application(
                id=str(uuid4()), job_id=job.id, answers={"cover_letter": answer}
            )
            db.save_application(app)

            review = ReviewWorkflow(db, llm_engine=llm)
            decision = await review.review_answers(
                app, job, {"cover_letter": answer}, profile
            )

            if decision.approved and job.apply_url:
                from src.models.forms import FormField
                from src.workflow.form_filler import FormFiller
                from src.workflow.submitter import Submitter

                form_filler = FormFiller(browser)
                submitter = Submitter(db, browser, form_filler)
                form_fields = [
                    FormField(
                        selector="#name",
                        field_type="text",
                        value=profile.name or "Alex Developer",
                    ),
                    FormField(selector="#resume", field_type="file", value="resume.txt"),
                ]
                await submitter.submit(app, job, form_fields, "#submit-button")
            elif decision.approved and not job.apply_url:
                print("Job has no apply URL — skipping submission.")
            else:
                print("Application cancelled.")

    db.close()


async def run_screen(config: object) -> None:
    """Run in screen-aware mode with global hotkey activation."""
    from src.screen.hotkey import GlobalHotkeyListener
    from src.screen.workflow import ScreenWorkflow

    db = Database(config.storage.database)
    db.initialize()

    profile_mgr = ProfileManager()
    profile = profile_mgr.load_profile_from_resume("resume.txt")

    provider = OllamaProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
    )
    prompt_loader = PromptLoader()
    llm = LLMEngine(provider, prompt_loader)
    generator = AnswerGenerator(llm, profile_mgr)

    workflow = ScreenWorkflow(config)
    workflow.initialize(
        profile_manager=profile_mgr,
        profile=profile,
        llm_engine=llm,
        answer_generator=generator,
        database=db,
    )

    async def on_hotkey() -> None:
        """Called when the hotkey is pressed."""
        print("\nHotkey detected! Scanning screen...")
        success = await workflow.run_once()
        if success:
            print("Application processed successfully!")
        else:
            print("Could not process application. Check logs for details.")

    hotkey_combo = getattr(config.screen, "hotkey", "cmd+j")
    listener = GlobalHotkeyListener(
        callback=on_hotkey, hotkey_combo=hotkey_combo, loop=asyncio.get_event_loop()
    )

    print("=" * 60)
    print("SCREEN-AWARE JOB APPLICATION ASSISTANT")
    print("=" * 60)
    print(f"\nHotkey: {hotkey_combo}")
    print("\nInstructions:")
    print("  1. Open a job posting in your browser")
    print("  2. Press the hotkey to scan and process")
    print("  3. Follow prompts for submission")
    print("\nPress Ctrl+C to exit.\n")

    listener.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        listener.stop()
        db.close()


async def run_scheduler(config: object) -> None:
    from src.scheduler.scheduler import Scheduler

    db = Database(config.storage.database)
    db.initialize()

    profile_mgr = ProfileManager()
    profile = profile_mgr.load_profile_from_resume("resume.txt")

    provider = OllamaProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
    )
    prompt_loader = PromptLoader()
    llm = LLMEngine(provider, prompt_loader)

    async with BrowserEngine(config.browser) as browser:
        sources = _build_sources(browser, config)
        evaluator = JobEvaluator(llm, profile_mgr)
        generator = AnswerGenerator(llm, profile_mgr)

        scheduler = Scheduler(
            sources=sources,
            database=db,
            evaluator=evaluator,
            answer_generator=generator,
            profile=profile,
            config=config.scheduler,
        )

        print(f"Starting scheduler (interval: {config.scheduler.interval_minutes} min)")
        print("Press Ctrl+C to stop.\n")

        try:
            await scheduler.run_forever()
        except KeyboardInterrupt:
            scheduler.stop()

    db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Career Assistant")
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="Run in periodic scheduler mode instead of interactive mode",
    )
    parser.add_argument(
        "--screen",
        action="store_true",
        help="Run in screen-aware mode with global hotkey activation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ConfigLoader().load()

    if args.screen:
        asyncio.run(run_screen(config))
    elif args.scheduler:
        asyncio.run(run_scheduler(config))
    else:
        asyncio.run(run_interactive(config))


if __name__ == "__main__":
    main()
