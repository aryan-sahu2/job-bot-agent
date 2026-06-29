# Job Link Aggregator + Smart Filter

Two scripts that replace complex automation with simple, practical workflows.

## Scripts

- **`aggregator.py`** — Searches LinkedIn, Greenhouse, Lever, Wellfound for jobs matching your config. Scores relevance with local LLM (Ollama). Outputs to `output/` dir.
- **`apply.py`** — Opens each job URL in a visible browser, parses the posting, generates a cover letter via Ollama, fills form fields automatically, saves a screenshot, and **pauses for your review** before submission.

## Quick Start

```bash
# Install
uv sync --all-extras
playwright install chromium

# Ensure Ollama is running
ollama serve

# 1. Update resume.txt with your profile (first line = your name)
# 2. Configure SearchConfig at the bottom of aggregator.py
# 3. Find jobs
uv run python aggregator.py

# 4. Review output/jobs_found_*.json, edit output/jobs_to_apply_*.txt
# 5. Apply (opens browser, you review before submit)
uv run python apply.py output/jobs_to_apply_*.txt
```

## Why This Works

- No bot detection — reads public listings, visible browser for submissions
- LLM filtering — automatically skips irrelevant jobs
- Human-in-the-loop — you review every application before it goes out
- Simple scripts, not complex architecture
- Local-first (Ollama, no cloud APIs)
- Resilient — skips errors, continues
