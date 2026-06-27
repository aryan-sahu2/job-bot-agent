# TASKS.md

# Development Roadmap

This document defines the implementation order for the AI Career Assistant.

The project should always be in a working state.

Only one milestone should be active at any time.

Future milestones exist to guide architecture, **not** current implementation.

---

# Project Status

**Current Phase**

> ✅ MVP Complete

---

# Milestone 0 — Project Foundation

Status: ✅ Complete

## Goals

* Repository structure
* Development tooling
* Configuration system
* Logging
* Testing setup
* Core data models

## Deliverables

* Project skeleton
* Configuration loader
* Logger
* Initial database
* Base models

## Definition of Done

* Repository builds successfully
* Tests execute
* Lint passes

---

# Milestone 1 — Browser Engine

Status: ✅ Complete

## Goals

Create a reusable browser automation layer.

## Responsibilities

* Launch browser
* Open pages
* Click
* Fill inputs
* Upload files
* Scroll
* Wait
* Screenshots

## Must Not

* Know about jobs
* Know about resumes
* Know about AI
* Know about storage

## Definition of Done

A simple script can launch Playwright and reliably automate a test page.

---

# Milestone 2 — Source Framework

Status: ✅ Complete

## Goals

Design the source interface.

Every source must return the same normalized `Job` model.

## Initial Source

* Wellfound

Future sources are intentionally excluded from implementation.

## Definition of Done

A Wellfound plugin returns normalized jobs without browser-specific logic leaking elsewhere.

---

# Milestone 3 — Storage

Status: ✅ Complete

## Goals

Persist application data.

Store:

* discovered jobs
* applications
* generated answers
* logs

SQLite is sufficient for the MVP.

## Deliverables

* SQLite-backed `Database` class
* Job CRUD (save, get, list)
* Application CRUD (save, get, list, update status)
* JSON serialization for nested fields
* Connection lifecycle management

## Definition of Done

* Tests pass (16 storage tests)
* Lint passes

---

# Milestone 4 — Resume & Profile

Status: ✅ Complete

## Goals

Load the user's professional profile.

Initially support:

* one resume
* one profile

Future support for multiple profiles is intentionally deferred.

## Deliverables

* `Profile` model (name, email, phone, title, skills, experience, education, urls, summary)
* `Resume` model (raw text, extracted profile, file path)
* `ResumeParser` — heuristic text-based resume extraction
* `ProfileManager` — loads resume file and returns parsed profile

## Definition of Done

* Tests pass (17 profile tests, 45 total)
* Lint passes

---

# Milestone 5 — Prompt System

Status: ✅ Complete

## Goals

Load prompts from the `/prompts` directory.

Support:

* answer generation
* rewriting
* job evaluation

Prompts should never be embedded directly inside Python files.

---

# Milestone 6 — LLM Engine

Status: ✅ Complete

## Goals

Execute prompts using local language models.

Initially support:

* Ollama

Future providers should require configuration changes only.

## Responsibilities

* prompt execution
* structured output
* retries
* parsing

---

# Milestone 7 — Job Evaluation

Status: ✅ Complete

## Goals

Compare discovered jobs against the active profile.

Generate:

* match score
* strengths
* missing skills
* summary

This stage should never modify the original job.

---

# Milestone 8 — Answer Generation

Status: ✅ Complete

## Goals

Generate personalized application responses.

Inputs:

* profile
* resume
* job description
* company

Outputs should be editable before submission.

## Deliverables

* `src/workflow/` package
* `AnswerGenerator` class — generates application answers via LLM
* Prompt variables built from `Job` and `Profile`
* Follows `_get_resume_path()` pattern from `JobEvaluator` for config-based resume discovery

## Definition of Done

* Tests pass (6 answer tests, 91 total)
* Lint passes

---

# Milestone 9 — Form Filling

Status: ✅ Complete

## Goals

Populate repetitive application fields.

Support:

* text fields
* dropdowns
* uploads
* checkboxes

Submission is not allowed in this milestone.

---

# Milestone 10 — Human Review

Status: ✅ Complete

## Goals

Pause the workflow before submission.

Allow the user to:

* approve
* edit
* rewrite
* cancel

No automatic submission.

## Deliverables

* `ReviewWorkflow` class — pauses pipeline for user review
* `ReviewDecision` model — captures approve/cancel and final answers
* CLI-based review workflow: approve, edit, rewrite (via LLM), cancel
* Application status updated: `draft` → `approved`, or `cancelled`

## Definition of Done

* Tests pass (13 review tests, 104 total)
* Lint passes

---

# Milestone 11 — Submission

Status: ✅ Complete

## Goals

Submit applications only after explicit approval.

Immediately log:

* timestamp
* company
* role
* source
* application status

## Deliverables

* `Submitter` class — orchestrates form filling and submission after approval
* `SubmissionError` — raised when preconditions (approved status, apply URL) aren't met
* Browser navigation, form filling, and click via existing `FormFiller` / `BrowserEngine`
* Database update: status → `submitted`, `submitted_at` → now
* Structured logging of submission event

## Definition of Done

* Tests pass
* Lint passes

---

# Milestone 12 — Scheduler

Status: 🔒 Locked

This milestone is intentionally postponed until the MVP is complete.

Future responsibilities:

* periodic scans
* job discovery
* recurring tasks

---

# Milestone 13 — Additional Sources

Status: 🔒 Locked

Future plugins:

* LinkedIn
* Gmail
* Naukri
* Greenhouse
* Lever
* Ashby
* Company portals

Each should implement the existing source interface.

---

# Milestone 14 — Intelligence

Status: 🔒 Locked

Future improvements:

* job ranking
* duplicate detection
* learning from approvals
* writing style adaptation
* recommendation engine

---

# Milestone 15 — Desktop Application

Status: 🔒 Locked

Future work:

* desktop interface
* dashboards
* analytics
* notifications
* application history

---

# Development Rules

Always work on the earliest incomplete milestone.

Do not begin a future milestone until the current one is fully complete.

Avoid partially implemented functionality.

Every completed milestone should leave the application in a working state.

---

# Definition of Done

A milestone is complete only when:

* Code works
* Tests pass
* Lint passes
* Documentation updated
* Manual verification completed

---

# Out of Scope (MVP)

The following features should **not** be implemented until after the MVP is complete:

* LinkedIn
* Gmail scanning
* Naukri
* Company watchlists
* Daily summaries
* AI learning
* Desktop UI
* Analytics
* Multiple profiles
* Multiple resumes
* Cloud deployment
* Distributed execution

Architecture should support these features, but implementation must wait.

---

# Final Rule

Whenever uncertain about what to build next:

1. Read this document.
2. Find the earliest incomplete milestone.
3. Complete it fully.
4. Update this document.
5. Move to the next milestone.

Never skip ahead.
