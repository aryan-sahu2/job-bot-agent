# AGENTS.md

# AI Career Assistant

## Purpose

This repository contains a local-first AI Career Assistant that helps discover, evaluate, prepare, and submit high-quality job applications while keeping the human fully in control.

The project is designed for AI-assisted development using OpenCode and local/free language models.

---

# Primary Objective

Build software that removes repetitive work from the job search process.

The assistant should:

- Discover jobs
- Collect jobs from multiple sources
- Evaluate job relevance
- Generate personalized application answers
- Fill repetitive application fields
- Pause for user review
- Submit applications only after explicit approval

The AI is an assistant.

It is **never** an autonomous job applicant.

---

# Core Principles

1. Human approval before every submission.
2. Local-first whenever practical.
3. Modular architecture.
4. Plugin-based integrations.
5. Small, testable components.
6. Working software over perfect architecture.
7. Build incrementally.
8. Never sacrifice readability for cleverness.

---

# Development Philosophy

Before writing code:

- Understand the task.
- Create a short implementation plan.
- Identify affected modules.
- Keep changes minimal.
- Finish one module before beginning another.

Do not jump ahead.

---

# Scope Management

Implement only what is currently required.

Future architecture is important.

Future implementation is not.

Example:

Good:
- Design plugin interfaces for multiple job sites.

Bad:
- Implement LinkedIn, Naukri, Greenhouse, Lever and Ashby together.

---

# Module Responsibilities

Every module must have one responsibility.

Examples:

Browser
- Launch browser
- Navigate
- Click
- Fill
- Upload
- Screenshot

Sources
- Discover jobs
- Normalize jobs

LLM
- Build prompts
- Execute model
- Parse responses

Workflow
- Orchestrate application lifecycle

Storage
- Persist data

Scheduler
- Trigger recurring tasks

Never mix responsibilities.

---

# Source Architecture

Every job source is independent.

Examples:

- Wellfound
- LinkedIn
- Gmail
- Naukri
- Greenhouse
- Lever
- Ashby
- Company career pages
- RSS feeds
- Google search

Every source must return the same normalized Job object.

Nothing outside the source should care where a job came from.

---

# Browser Rules

The browser layer only automates browsers.

Allowed:

- click
- type
- upload
- scroll
- wait
- screenshot

Not allowed:

- business logic
- AI prompts
- job ranking
- storage decisions

---

# LLM Rules

Always separate:

- prompt construction
- model execution
- response parsing

Prompt templates belong in `/prompts`.

Never hardcode prompts inside Python files.

Prefer structured JSON outputs.

Retry malformed responses safely.

Changing the model should require configuration only.

---

# Prompt Inputs

Prompt generation may use:

- resume
- profile
- job description
- company
- writing style
- previous approved answers

Never invent experience.

Never fabricate achievements.

If information is missing, ask the user.

---

# Human Review

Applications must always stop before submission.

The user must be able to:

- Review
- Edit
- Rewrite
- Skip
- Approve

Automatic submission is forbidden.

---

# Coding Standards

Always:

- Python 3.12+
- Type hints
- Dataclasses or Pydantic where appropriate
- Async where appropriate
- Small functions
- Small classes
- Clear names

Avoid:

- Giant files
- God classes
- Premature abstractions
- Hidden side effects

---

# Error Handling

Do not crash unnecessarily.

Retry transient failures.

Capture screenshots for browser failures.

Log useful context.

Surface meaningful errors.

---

# Testing

Every completed module should include:

- Unit tests
- Manual verification
- Lint passing

A task is not complete until all three pass.

---

# Build Order

Build in this order.

1. Core models
2. Configuration
3. Storage
4. Browser engine
5. Source interface
6. Wellfound source
7. Resume parser
8. Profile manager
9. LLM engine
10. Prompt system
11. Job evaluator
12. Answer generation
13. Form filling
14. Review workflow
15. Submission
16. Scheduler
17. Memory
18. Additional sources

Do not skip ahead.

---

# Definition of Done

A feature is complete only when:

- Code works
- Tests pass
- Lint passes
- Manual verification passes
- Documentation updated

---

# Final Rule

Prefer shipping one complete feature over five partially built ones.

Incremental progress beats unfinished architecture.

---

# Quick Reference

## Setup

```bash
# Install dependencies
uv sync --all-extras

# If after uv sync, python/python3 fail with ModuleNotFoundError, re-activate:
source .venv/bin/activate

# On macOS, use `python3` if `python` is not found in venv
```

## Commands

```bash
# Run all tests (~2 min, 151 tests)
uv run pytest tests/ --tb=short

# Run specific test file (fast, ~10-20s)
uv run pytest tests/test_scheduler.py -x -v

# Run lint
uv run ruff check src/ tests/

# Run formatter
uv run ruff format src/ tests/

# Run the app
uv run python run.py              # interactive mode
uv run python run.py --scheduler  # periodic scheduler mode
```

**Note:** Always prefer `uv run python` over bare `python` or `python3` to ensure the correct venv is used. After `uv sync` recreates `.venv`, you must re-activate it (`source .venv/bin/activate`) or use `uv run`.

**Scheduler requirements:** The scheduler needs Ollama running locally (`ollama serve`) and Playwright browsers installed (`playwright install`) for real job discovery. Tests use mocks and require neither.

## Project State

Milestones 0–13 are complete. The project has a full pipeline from job discovery through submission.

Completed modules:
- `src/models/` — Job, Application, Evaluation, FormField
- `src/config/` — YAML config loader with Pydantic models
- `src/storage/` — SQLite Database with Job/Application CRUD
- `src/browser/` — Playwright-based BrowserEngine
- `src/sources/` — Wellfound, Greenhouse, Lever, LinkedIn (all implement Source ABC)
- `src/profile/` — ResumeParser, ProfileManager
- `src/llm/` — LLMEngine, OllamaProvider
- `src/prompts/` — PromptLoader (reads from `/prompts`)
- `src/evaluator/` — JobEvaluator (LLM-based scoring)
- `src/workflow/` — AnswerGenerator, FormFiller, ReviewWorkflow, Submitter
- `src/scheduler/` — Scheduler (periodic job discovery)

## Key Conventions

- All source classes extend `Source` ABC and return `list[Job]`
- Config lives in `config/default.yaml`, loaded via `ConfigLoader`
- Tests use mock objects for browser/LLM (no real network calls)
- Async throughout — use `pytest-asyncio` for async tests