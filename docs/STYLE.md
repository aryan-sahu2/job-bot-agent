# STYLE.md

# Coding Style Guide

## Purpose

This document defines the coding standards used throughout the project.

Consistency is more important than personal preference.

Whenever multiple valid implementations exist, prefer the style described here.

---

# General Principles

Write code for humans first.

Optimize for:

* readability
* maintainability
* testability
* simplicity

Avoid clever solutions that reduce clarity.

---

# Python Version

Use:

* Python 3.12+

Take advantage of modern language features where appropriate.

---

# Type Hints

Always use type hints.

Good:

```python
def evaluate(job: Job) -> Evaluation:
    ...
```

Avoid:

```python
def evaluate(job):
    ...
```

---

# Function Design

Functions should do one thing.

Prefer:

* 10–30 lines
* descriptive names
* explicit inputs
* explicit outputs

Avoid functions longer than ~50 lines unless absolutely necessary.

---

# Class Design

Classes should represent one responsibility.

Prefer small focused classes over large service objects.

Avoid "God Classes."

---

# Naming

Use descriptive names.

Good:

* JobEvaluator
* ResumeParser
* BrowserSession
* AnswerGenerator

Avoid:

* Utils
* Manager
* Helper
* Misc

Names should communicate intent.

---

# File Organization

One file should generally contain one primary responsibility.

Avoid files containing unrelated classes.

---

# Imports

Use absolute imports within the project.

Group imports:

1. Standard library
2. Third-party packages
3. Local modules

Remove unused imports.

---

# Comments

Write comments explaining **why**, not **what**.

Good:

```python
# Retry because Wellfound occasionally returns empty pages.
```

Avoid:

```python
# Increment i
i += 1
```

The code should explain itself.

---

# Logging

Use structured logging.

Log:

* browser failures
* retries
* important workflow transitions
* submission events

Avoid excessive logging inside loops.

Never log secrets.

---

# Exceptions

Raise meaningful exceptions.

Catch exceptions where recovery is possible.

Do not silently ignore errors.

Prefer:

```python
raise BrowserTimeoutError(...)
```

instead of generic exceptions.

---

# Async Programming

Use async where it improves I/O performance.

Examples:

* browser automation
* HTTP requests
* LLM calls

Avoid unnecessary async complexity for purely synchronous code.

---

# Configuration

Do not hardcode:

* paths
* model names
* timeouts
* API endpoints
* browser settings

Configuration belongs in the `config/` directory.

---

# Prompt Management

Prompts belong in `/prompts`.

Never embed long prompts inside Python files.

Prompt templates should be reusable and version controlled.

---

# Data Models

Prefer dataclasses or Pydantic models for structured data.

Avoid passing unstructured dictionaries between modules.

---

# Testing

Every new module should include tests.

Test:

* expected behavior
* edge cases
* invalid input
* failure paths

Code is not complete until tests pass.

---

# Formatting

Use:

* Ruff
* Black-compatible formatting
* Consistent line lengths

Do not manually fight the formatter.

---

# Documentation

Public classes and functions should include concise docstrings.

Keep documentation synchronized with implementation.

---

# Preferred Architecture

Favor:

* composition
* dependency injection
* interfaces
* small modules

Avoid tightly coupled components.

---

# Code Review Checklist

Before considering work complete, verify:

* Type hints added
* Functions remain small
* No duplicated logic
* Tests added
* Lint passes
* Documentation updated
* Configuration externalized
* No dead code
* No TODOs left behind without explanation

---

# Final Principle

Future contributors—including AI coding assistants—should be able to understand any file within a few minutes.

If a solution feels clever but difficult to understand, rewrite it.
