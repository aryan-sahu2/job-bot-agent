#!/usr/bin/env python3
"""Main entry point for the job bot."""

import argparse
import asyncio
import logging
import sys

from src.browser.engine import BrowserEngine, BrowserError
from src.config.loader import ConfigLoader
from src.evaluator.evaluator import JobEvaluator
from src.llm.engine import LLMEngine
from src.llm.ollama import OllamaProvider
from src.logging.setup import setup_logger
from src.profile.manager import ProfileManager
from src.prompts.loader import PromptLoader
from src.scheduler.scheduler import Scheduler
from src.screen.hotkey import GlobalHotkeyListener
from src.screen.workflow import ScreenWorkflow
from src.sources.greenhouse import GreenhouseSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.wellfound import WellfoundSource
from src.storage.database import Database
from src.workflow.answer import AnswerGenerator

logger = logging.getLogger("job-bot")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Job Application Bot")
    parser.add_argument("--screen", action="store_true", help="Run screen-aware assistant")
    parser.add_argument("--scheduler", action="store_true", help="Run scheduler")
    args = parser.parse_args()

    setup_logger()
    config = ConfigLoader().load()

    # --- SHARED BROWSER via CDP (for screen mode) ---
    # When using --screen, we connect to the user's existing browser
    # instead of launching a new one. This ensures the screen workflow
    # and any sources share the SAME browser instance.
    browser = BrowserEngine(config.browser)

    if args.screen:
        try:
            await browser.connect_over_cdp("http://localhost:9222")
            logger.info("Connected to existing browser via CDP")
        except BrowserError as e:
            logger.error(
                "Failed to connect to browser via CDP. "
                "Make sure you started Brave/Chrome with: "
                "--remote-debugging-port=9222"
            )
            logger.error("%s", e)
            sys.exit(1)
    else:
        # Normal mode: launch a new browser
        await browser.start()

    # --- Initialize components ---
    db = Database(config.storage.database)
    db.initialize()

    profile_manager = ProfileManager()
    profile = profile_manager.load_profile_from_resume("resume.txt")

    llm_provider = OllamaProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        timeout=config.llm.timeout,
    )
    llm_engine = LLMEngine(llm_provider, PromptLoader())
    answer_generator = AnswerGenerator(llm_engine, profile_manager)
    evaluator = JobEvaluator(llm_engine, profile_manager)

    # --- Screen mode ---
    if args.screen:
        screen_workflow = ScreenWorkflow(config, browser=browser)
        screen_workflow.initialize(
            profile_manager=profile_manager,
            profile=profile,
            llm_engine=llm_engine,
            answer_generator=answer_generator,
            database=db,
        )

        async def on_hotkey() -> None:
            await screen_workflow.run_once()

        hotkey = GlobalHotkeyListener(
            callback=on_hotkey,
            hotkey_combo=config.screen.hotkey,
            loop=asyncio.get_running_loop(),
        )
        hotkey.start()

        print("=" * 60)
        print("SCREEN-AWARE JOB APPLICATION ASSISTANT")
        print("=" * 60)
        print(f"Hotkey: {config.screen.hotkey}")
        print("\nInstructions:")
        print("  1. Open a job posting in your browser")
        print("  2. Press the hotkey to scan and process")
        print("  3. Follow prompts for submission")
        print("\nPress Ctrl+C to exit.\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            hotkey.stop()
        finally:
            await browser.close()
        return

    # --- Scheduler mode ---
    if args.scheduler:
        sources = []

        if config.greenhouse.enabled:
            sources.append(GreenhouseSource(browser, config.greenhouse.board_slugs))
        if config.lever.enabled:
            sources.append(LeverSource(browser, config.lever.company_slugs))
        if config.linkedin.enabled:
            sources.append(LinkedInSource(
                browser,
                keywords=config.linkedin.keywords,
                location=config.linkedin.location,
            ))

        scheduler = Scheduler(
            sources=sources,
            database=db,
            evaluator=evaluator,
            answer_generator=answer_generator,
            profile=profile,
            config=config.scheduler,
        )

        try:
            await scheduler.run_forever()
        except KeyboardInterrupt:
            scheduler.stop()
        finally:
            await browser.close()
        return

    # Default: print help
    parser.print_help()
    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())