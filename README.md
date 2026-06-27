# AI Career Assistant

A local-first AI-powered assistant that helps discover, evaluate, prepare, and submit high-quality job applications while keeping the user in complete control.

The project is designed to automate repetitive work—not decision making.

---

# Why This Project Exists

Applying for jobs is highly repetitive.

Every application involves tasks like:

* Searching multiple job boards
* Reading similar job descriptions
* Comparing opportunities
* Uploading the same resume
* Filling identical profile information
* Answering repeated application questions
* Writing personalized responses
* Tracking submitted applications

Most of this work doesn't require creativity—it requires time.

The AI Career Assistant removes this repetitive effort while ensuring every important decision remains with the user.

---

# Guiding Principles

* Human-in-the-loop
* Local-first whenever practical
* Modular architecture
* Plugin-based integrations
* Extensible by design
* Quality over quantity
* Transparency over automation

The assistant never submits an application without explicit approval.

---

# Weekend MVP

The first version intentionally focuses on one complete workflow.

Supported:

* Python 3.12+
* Playwright
* Wellfound
* Ollama
* Local LLMs
* Resume upload
* Job description parsing
* Personalized answer generation
* Auto-fill repetitive fields
* Human review
* Manual approval
* Application logging

Not supported yet:

* LinkedIn
* Naukri
* Gmail scanning
* Greenhouse
* Lever
* Ashby
* Company portals
* Multiple profiles
* Desktop UI
* Analytics
* Watchlists
* Scheduling

These future features influence today's architecture but are **not** part of the MVP implementation.

---

# Long-Term Vision

The long-term goal is to build a personal AI Career Assistant capable of:

* Discovering jobs automatically
* Monitoring multiple job sources
* Reading Gmail job alerts
* Ranking opportunities
* Learning user preferences
* Generating personalized application answers
* Filling repetitive application fields
* Tracking applications
* Learning from approved responses
* Supporting multiple resumes and career profiles
* Running primarily on local language models

The browser automation framework should also be reusable for future automation workflows beyond job applications.

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

Wellfound Gmail LinkedIn Company Sites

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

Every source produces the same normalized `Job` object.

The rest of the system should never care where the job originated.

---

# Planned Job Sources

Future plugins may include:

* Wellfound
* LinkedIn Jobs
* Gmail
* Naukri
* Instahyre
* Cutshort
* Greenhouse
* Lever
* Ashby
* Workday
* Company career portals
* Google Search
* RSS feeds

Each source remains completely independent.

---

# Technology Stack

| Area               | Technology                   |
| ------------------ | ---------------------------- |
| Language           | Python 3.12+                 |
| Browser Automation | Playwright                   |
| LLM                | Ollama                       |
| Recommended Models | Gemma 3, Qwen 2.5            |
| Storage            | SQLite                       |
| Testing            | Pytest                       |
| Formatting         | Ruff                         |
| Configuration      | YAML / Environment Variables |

---

# Development Philosophy

The project is intentionally built one complete module at a time.

Each module should:

* Have one responsibility
* Be independently testable
* Minimize dependencies
* Be easy to replace
* Be easy to extend

Working software always takes priority over speculative architecture.

---

# Human Review Workflow

Every application follows the same process:

```
Discover Job
      ↓
Evaluate Match
      ↓
Generate Answers
      ↓
Fill Application
      ↓
Pause
      ↓
Review
      ↓
Approve
      ↓
Submit
      ↓
Log
```

Submission never occurs without user approval.

---

# Repository Structure

```
job-bot/

├── AGENTS.md
├── README.md
├── .opencode-rules

├── docs/
│   ├── DESIGN.md
│   ├── PROJECT_CONTEXT.md
│   ├── STYLE.md
│   └── TASKS.md

├── prompts/
├── src/
├── tests/
├── storage/
└── config/
```

---

# MVP Success Criteria

The first version is considered complete when it can:

* Launch a browser
* Search Wellfound
* Discover jobs
* Parse job descriptions
* Parse the user's resume
* Generate personalized answers
* Fill repetitive fields
* Pause for review
* Submit only after approval
* Log completed applications

Only after achieving these goals should additional job sources be implemented.

---

# Future Roadmap

* Gmail integration
* LinkedIn plugin
* Naukri plugin
* Company watchlists
* Daily job summaries
* AI job ranking
* Multiple user profiles
* Resume management
* Writing-style learning
* Desktop application
* Analytics dashboard
* Calendar integration
* Email notifications

---

# License

This project is currently intended as a personal productivity and learning tool.

The architecture is designed so it can later evolve into a reusable, extensible browser automation framework for AI-assisted workflows.
