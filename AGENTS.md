# AGENTS.md

# Job Link Aggregator + Smart Filter

Two scripts that replace the old complex architecture. Simple, practical, and human-in-the-loop.

## Scripts

### `aggregator.py`
- Searches LinkedIn, Greenhouse, Lever, Wellfound for jobs matching your config
- Scores relevance using a local LLM (Ollama)
- Outputs `jobs_found.json` (full data) and `jobs_to_apply.txt` (URLs for apply.py)

### `apply.py`
- Opens each job URL in a visible browser
- Parses the job posting (title, company, description)
- Generates a personalized cover letter via Ollama
- Fills application form fields automatically
- Saves a screenshot
- **Pauses for your review** before submission

## Workflow

```bash
# 1. Update resume.txt with your profile
# 2. Configure SearchConfig in aggregator.py
# 3. Find jobs
uv run python aggregator.py

# 4. Review jobs_found.json, edit jobs_to_apply.txt
# 5. Apply
uv run python apply.py jobs_to_apply.txt
```

## Principles

1. Human approval before every submission
2. Local-first (Ollama, no cloud APIs)
3. No bot detection fighting — reads public listings, submits with visible browser
4. Simple scripts, not complex architecture
5. Resilient — skips errors, continues

## Setup

```bash
uv sync --all-extras
playwright install chromium
ollama serve  # Ensure Ollama is running
```

## Key Conventions

- `resume.txt` — first line is your name, contains email/phone and full profile text
- `SearchConfig` in `aggregator.py` controls keywords, location, salary threshold
- Screenshots saved to `screenshots/`
- Output files: `jobs_found.json`, `jobs_to_apply.txt`
