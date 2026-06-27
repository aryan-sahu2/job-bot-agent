import asyncio
import logging

from src.browser.engine import BrowserEngine
from src.config.loader import ConfigLoader
from src.evaluator.evaluator import JobEvaluator
from src.llm.engine import LLMEngine
from src.llm.ollama import OllamaProvider
from src.profile.manager import ProfileManager
from src.prompts.loader import PromptLoader
from src.sources.greenhouse import GreenhouseSource
from src.sources.lever import LeverSource
from src.sources.linkedin import LinkedInSource
from src.sources.wellfound import WellfoundSource
from src.storage.database import Database
from src.workflow.answer import AnswerGenerator
from src.workflow.review import ReviewWorkflow

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("job-bot")


async def main():
    config = ConfigLoader().load()
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
        jobs = []

        wellfound = WellfoundSource(browser)
        wellfound_jobs = await wellfound.discover()
        jobs.extend(wellfound_jobs)

        if config.greenhouse.enabled and config.greenhouse.board_slugs:
            greenhouse = GreenhouseSource(browser, config.greenhouse.board_slugs)
            jobs.extend(await greenhouse.discover())

        if config.lever.enabled and config.lever.company_slugs:
            lever = LeverSource(browser, config.lever.company_slugs)
            jobs.extend(await lever.discover())

        if config.linkedin.enabled and config.linkedin.keywords:
            linkedin = LinkedInSource(
                browser, config.linkedin.keywords, config.linkedin.location
            )
            jobs.extend(await linkedin.discover())

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

        for job in jobs:
            db.save_job(job)

            evaluator = JobEvaluator(llm, profile_mgr)
            evaluation = await evaluator.evaluate(job, profile)
            print(f"\n{'=' * 60}")
            print(f"{job.title} @ {job.company}")
            print(f"Match: {evaluation.match_score}/100")
            print(f"Strengths: {', '.join(evaluation.strengths)}")
            print(f"Missing: {', '.join(evaluation.missing_skills)}")
            print(f"Summary: {evaluation.summary}")

            generator = AnswerGenerator(llm, profile_mgr)
            answer = await generator.generate(job, profile)

            from uuid import uuid4

            from src.models.application import Application

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


if __name__ == "__main__":
    asyncio.run(main())
