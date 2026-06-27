# DESIGN.md

# AI Career Assistant Architecture

## Purpose

This document describes the architecture of the AI Career Assistant.

It explains how the system is organized, how information flows through it, and why each module exists.

This is **not** an implementation guide.

---

# Design Goals

The architecture should be:

* Modular
* Local-first
* Easy to extend
* Easy to test
* Easy to replace individual components
* Independent of specific job websites
* Independent of specific LLM providers

The MVP should remain small while allowing future expansion without major redesign.

---

# Core Philosophy

The assistant is composed of independent modules.

Each module has a single responsibility.

Modules communicate using shared data models instead of direct knowledge of each other.

Whenever possible:

```
Input
    ↓
Transform
    ↓
Output
```

instead of

```
Input
    ↓
Business Logic
    ↓
Browser
    ↓
Database
    ↓
LLM
    ↓
Output
```

Loose coupling is preferred over convenience.

---

# High-Level Architecture

```
                    Scheduler
                         │
                         ▼

                  Job Sources
       ┌──────────┬──────────┬──────────┐
       │          │          │          │
       ▼          ▼          ▼          ▼

   Wellfound   Gmail   LinkedIn   Company Sites

                 │
                 ▼

            Job Collector

                 │
                 ▼

            Job Evaluator

                 │
                 ▼

         Application Queue

                 │
                 ▼

          Browser Automation

                 │
                 ▼

          Human Review

                 │
                 ▼

             Submission

                 │
                 ▼

           Application Log
```

Every discovered job eventually follows the exact same pipeline.

The origin of the job becomes irrelevant after normalization.

---

# Normalized Job Model

Every source must return the same structure.

Example:

```python
Job
├── id
├── source
├── company
├── title
├── location
├── employment_type
├── salary
├── description
├── skills
├── apply_url
├── posted_date
└── metadata
```

This allows every downstream module to remain source-independent.

---

# Module Overview

## Scheduler

Responsibilities:

* Run periodic tasks
* Trigger job discovery
* Prevent duplicate scans

The scheduler never evaluates jobs.

---

## Sources

Responsibilities:

* Discover jobs
* Parse source-specific information
* Return normalized Job objects

Examples:

* Wellfound
* Gmail
* LinkedIn
* Naukri
* Company websites

Every source implements the same interface.

---

## Job Collector

Responsibilities:

* Receive jobs from sources
* Remove duplicates
* Persist jobs
* Forward new jobs for evaluation

The collector performs no AI operations.

---

## Job Evaluator

Responsibilities:

* Compare jobs against the active profile
* Calculate match score
* Identify missing skills
* Rank opportunities

Output:

```
Job
+
Evaluation
```

---

## Browser Automation

Responsibilities:

* Launch browser
* Navigate
* Click
* Fill forms
* Upload files
* Scroll
* Capture screenshots

Browser automation knows nothing about:

* resumes
* jobs
* prompts
* AI
* storage

It only executes browser actions.

---

## LLM Engine

Responsibilities:

* Load prompts
* Execute models
* Parse structured outputs
* Retry malformed responses

The LLM layer should never know where prompts came from.

Changing models should require configuration only.

---

## Prompt Library

Prompts are stored separately from code.

Examples:

```
prompts/

answer_generation.md

job_matching.md

rewrite.md

company_analysis.md
```

Prompt engineering should never require changing Python code.

---

## Profile Manager

The profile manager stores reusable user information.

Initially only one profile is required.

Eventually it may support:

* resumes
* skills
* locations
* salary expectations
* writing style
* portfolios
* links

---

## Review Workflow

Before submission, the assistant pauses.

The user may:

* approve
* edit
* rewrite
* skip

No automatic submission is permitted.

---

## Storage

Persistent storage is responsible for:

* discovered jobs
* applications
* generated answers
* logs
* cache

Business logic should never depend on storage implementation.

SQLite is sufficient for the MVP.

---

# Job Lifecycle

Every job moves through predictable stages.

```
Discovered

↓

Normalized

↓

Stored

↓

Evaluated

↓

Ranked

↓

Queued

↓

Answer Generation

↓

Browser Automation

↓

Human Review

↓

Approved

↓

Submitted

↓

Logged
```

Every transition should be observable and recoverable.

---

# Plugin Architecture

Every source is isolated.

```
Source Interface

├── Wellfound

├── LinkedIn

├── Gmail

├── Naukri

├── Greenhouse

├── Lever

├── Ashby
```

Adding a new source should require creating a new plugin rather than modifying existing code.

---

# Error Handling

Errors should remain local whenever possible.

Examples:

* Browser crash
* LLM timeout
* Network failure
* Invalid HTML

A failure in one source must not stop the entire assistant.

Retry transient failures.

Log permanent failures.

---

# Future Expansion

The architecture should naturally support:

* Multiple resumes
* Multiple user profiles
* Company watchlists
* Gmail job alerts
* Daily summaries
* AI job ranking
* Calendar integration
* Desktop application
* Additional job platforms

These features should require adding modules—not redesigning existing ones.

---

# Architecture Principles

Every design decision should follow these principles:

1. One responsibility per module.
2. Prefer composition over coupling.
3. Normalize data early.
4. Keep browser automation generic.
5. Keep prompts outside code.
6. Human approval before submission.
7. Local-first whenever practical.
8. Build incrementally.
9. Optimize for maintainability.
10. Favor working software over perfect abstractions.
