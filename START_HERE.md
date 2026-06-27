# START_HERE.md

# AI Career Assistant

## Read This First

If you are an AI coding assistant (OpenCode, Claude Code, Cursor, Gemini CLI, etc.), read this file before making any changes.

Your goal is to continue building this project incrementally while preserving the existing architecture.

Do not redesign the project unless a genuine architectural flaw is discovered.

---

# Reading Order

Always read the following files in this order:

1. AGENTS.md
2. docs/TASKS.md
3. docs/DESIGN.md
4. docs/STYLE.md
5. docs/PROJECT_CONTEXT.md

Do not skip this order.

---

# Your Workflow

Every coding session should follow these steps.

## Step 1

Read the documentation.

Understand:

* current milestone
* architecture
* coding standards

Do not immediately generate code.

---

## Step 2

Determine the current milestone from:

docs/TASKS.md

Only work on the earliest incomplete milestone.

Do not skip milestones.

---

## Step 3

Before writing code, produce a short implementation plan.

The plan should include:

* files to create
* files to modify
* responsibilities
* assumptions
* potential risks

Wait for approval before continuing if the implementation changes project structure.

---

## Step 4

Generate code.

Follow STYLE.md.

Keep changes focused.

Avoid unrelated refactoring.

---

## Step 5

After implementation, verify:

* code compiles
* tests pass
* lint passes

If something fails, fix it before moving forward.

---

## Step 6

Update documentation only if behavior changed.

Do not rewrite documentation unnecessarily.

---

# Architecture Rules

Always preserve these principles.

* One responsibility per module.
* Browser automation contains no business logic.
* Sources own website-specific logic.
* Jobs are normalized immediately.
* Prompts live in `/prompts`.
* Configuration lives in `/config`.
* LLM providers are interchangeable.
* Human approval is mandatory before submission.

---

# Coding Rules

Always:

* use Python 3.12+
* use type hints
* keep functions small
* keep classes focused
* write tests
* prefer composition
* write readable code

Avoid:

* giant files
* hidden side effects
* duplicated logic
* premature optimization

---

# What NOT To Do

Do not:

* redesign the architecture
* add future roadmap features
* implement locked milestones
* hardcode configuration
* embed prompts inside Python
* auto-submit applications
* fabricate user information

---

# Project Goal

The objective is **not** to build the largest job automation tool.

The objective is to build one polished workflow that can later be expanded.

Working software is always more valuable than unfinished architecture.

---

# Development Order

Always follow the roadmap in `docs/TASKS.md`.

At the time of writing, the expected order is:

1. Foundation
2. Browser Engine
3. Source Framework
4. Storage
5. Resume & Profile
6. Prompt System
7. LLM Engine
8. Job Evaluation
9. Answer Generation
10. Form Filling
11. Human Review
12. Submission

Everything after that is future work.

---

# If You Are Unsure

When uncertain:

1. Read TASKS.md again.
2. Choose the earliest incomplete milestone.
3. Build only that milestone.
4. Keep the application working.
5. Stop when the milestone is complete.

Never guess what should come next.

---

# Session Checklist

Before ending a session, confirm:

* [ ] Current milestone completed
* [ ] Tests passing
* [ ] Lint passing
* [ ] Documentation updated (if required)
* [ ] No unrelated code changes
* [ ] Project still builds successfully

Only then move to the next milestone.