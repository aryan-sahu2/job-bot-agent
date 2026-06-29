# Job Link Aggregator + Smart Filter

Two scripts that replace complex automation with simple, practical workflows.

## Scripts

- **`src/cli.py`** — Searches LinkedIn, Indeed, Wellfound, Naukri for jobs matching your config. Scores relevance with local LLM (Ollama). Uses `config.json` as single source of truth; CLI flags are temporary overrides.
- **`src/apply.py`** — Opens each job URL in a visible browser, parses the posting, generates a cover letter via Ollama, fills application form fields automatically, saves a screenshot, and **pauses for your review** before submission. Detects LinkedIn login walls and skips them.

## Quick Start

```bash
# Install
uv sync --all-extras
playwright install chromium

# Ensure Ollama is running
ollama serve

# 1. Update resume.txt with your profile (first line = your name)
# 2. First run — creates config.json automatically
uv run python -m src.cli

# 3. Edit config.json with your preferences
# 4. Run again → jobs appear in output/
uv run python -m src.cli

# 5. Review output/jobs_found_*.json, edit output/jobs_to_apply_*.txt
# 6. Apply (opens browser, you review before submit)
uv run python src/apply.py output/jobs_to_apply_*.txt
```

## Configuration

Edit `config.json` at the project root. Key settings:

| Field | Description |
|---|---|
| `keywords` | Job title / search keywords |
| `location` | "Remote" or a city |
| `min_salary_lakhs` | Minimum salary in LPA (Indian market) |
| `hours_since_posted` | Recency filter (hours) |
| `exclude_keywords` | Keywords to filter out |
| `greenhouse_boards` | Company slugs for Greenhouse ATS |
| `lever_slugs` | Company slugs for Lever ATS |
| `max_jobs_per_source` | Max jobs to scrape per source |
| `llm_model` | Ollama model name (e.g. gemma3, llama3) |
| `resume_path` | Path to your resume/profile text file |

## CLI Overrides

Override any config value for a single run:

```bash
# Override keywords and hours
uv run python -m src.cli --hours 2 --keywords "Backend Engineer"

# Use a different config file
uv run python -m src.cli --config ~/job-bot-config.json
```

## CDP Mode (Real Chrome)

For sites that require login (LinkedIn Easy Apply), connect to your real Chrome:

```bash
# 1. Launch real Chrome with remote debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome"

# 2. Log into LinkedIn manually in that window
# 3. Run apply.py with --cdp flag
uv run python src/apply.py --cdp output/jobs_to_apply_*.txt
```

## Why This Works

- No bot detection fighting — reads public listings, visible browser for submissions
- LinkedIn login walls detected and skipped automatically
- LLM filtering — automatically skips irrelevant jobs
- Human-in-the-loop — you review every application before it goes out
- Simple scripts, not complex architecture
- Local-first (Ollama, no cloud APIs)
- Resilient — skips errors, continues
