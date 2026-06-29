# AGENTS.md

# Job Link Aggregator + Smart Filter

Two scripts that replace the old complex architecture. Simple, practical, and human-in-the-loop.

## Scripts

### `aggregator.py`
- Searches LinkedIn, Greenhouse, Lever, Wellfound for jobs matching your config
- Scores relevance using a local LLM (Ollama)
- Outputs `output/jobs_found_*.json` (full data) and `output/jobs_to_apply_*.txt` (URLs for apply.py)

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

# 4. Review output/jobs_found_*.json, edit output/jobs_to_apply_*.txt
# 5. Apply
uv run python apply.py output/jobs_to_apply_*.txt
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
- Output files: `output/jobs_found_*.json`, `output/jobs_to_apply_*.txt`
