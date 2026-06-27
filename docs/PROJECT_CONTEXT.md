# PROJECT_CONTEXT.md

# Project Context

This document provides project-specific context for AI coding assistants.

It explains who the software is being built for, what problems it solves, and the guiding assumptions behind implementation decisions.

This file intentionally avoids architectural details already covered in `DESIGN.md`.

---

# Primary User

The primary user is the developer of this application.

The assistant should optimize for a technically proficient user who wants to automate repetitive parts of the job search while retaining complete control over every application.

---

# Problem Statement

Modern job searching involves significant repetitive work.

Typical activities include:

* discovering jobs
* reading similar job descriptions
* evaluating relevance
* uploading resumes
* filling identical forms
* answering repeated questions
* tracking submitted applications

The software exists to reduce repetition—not replace human judgement.

---

# Product Philosophy

The assistant should behave like a trusted career assistant.

It should:

* save time
* reduce manual effort
* explain decisions
* ask for confirmation
* remain transparent

It should never:

* fabricate experience
* exaggerate skills
* submit applications automatically
* make irreversible decisions without approval

---

# Development Philosophy

The project is intentionally developed in small iterations.

Each completed feature should leave the application in a working state.

Avoid partially implemented systems.

Build vertically rather than horizontally.

Complete one workflow before starting the next.

---

# MVP Focus

The first milestone is intentionally narrow.

Support only:

* Wellfound
* Resume parsing
* Job parsing
* Personalized answer generation
* Browser automation
* Human review
* Manual submission
* Application logging

Every additional feature should be deferred until this workflow is complete.

---

# Long-Term Vision

The assistant should eventually become a centralized career platform.

Future capabilities may include:

* multiple job sources
* Gmail integration
* company watchlists
* recurring job discovery
* multiple resumes
* multiple career profiles
* daily summaries
* interview preparation
* application analytics
* writing style learning

These goals should influence architecture but not current implementation.

---

# Writing Style

Generated text should sound natural.

Prefer:

* concise language
* technical accuracy
* honest experience
* practical examples

Avoid:

* buzzwords
* generic AI phrasing
* exaggerated enthusiasm
* fabricated accomplishments

Generated writing should resemble an experienced engineer explaining real work.

---

# Decision Making

When several implementation approaches are possible:

Prefer:

* simplicity
* readability
* modularity
* maintainability
* explicit behaviour

Avoid:

* unnecessary abstractions
* premature optimization
* hidden magic
* overengineering

---

# AI Expectations

When contributing code:

* understand the existing module first
* keep changes small
* preserve modularity
* avoid unrelated refactoring
* update documentation when behaviour changes
* write code that is easy to test

Always prioritize a working implementation over speculative improvements.

---

# Success Definition

The project succeeds when it consistently helps users produce better job applications with less repetitive effort while preserving complete human control over every important decision.

Every implementation decision should support that objective.
