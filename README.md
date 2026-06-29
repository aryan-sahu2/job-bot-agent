# Job Link Aggregator + Smart Filter

Two scripts that replace complex automation with simple, practical workflows.

## Scripts

- **`src/cli.py`** (or `aggregator.py`) — Searches LinkedIn, Indeed, Wellfound, Naukri for jobs matching your config. Scores relevance with local LLM (Ollama). Supports recency filter, startup filter, LPA/INR salary parsing. Outputs to `output/` dir.
- **`src/apply.py`** — Opens each job URL in a visible browser, parses the posting, generates a cover letter via Ollama, fills application form fields automatically, saves a screenshot, and **pauses for your review** before submission. Detects LinkedIn login walls and skips them.

## Quick Start

```bash
# Install
uv sync --all-extras
playwright install chromium

# Ensure Ollama is running
ollama serve

# 1. Update resume.txt with your profile (first line = your name)
# 2. Find jobs
uv run python -m src.cli --hours 4 --startup --min-lpa 15 --location "Remote" --keywords "Full Stack Engineer"

# 3. Review output/jobs_found_*.json, edit output/jobs_to_apply_*.txt
# 4. Apply (opens browser, you review before submit)
uv run python src/apply.py output/jobs_to_apply_*.txt
```

## CLI Examples

```bash
# Full options
uv run python -m src.cli \
  --keywords "Full Stack Developer" \
  --location "Remote" \
  --hours 4 \
  --startup \
  --min-lpa 15 \
  --exclude "php,wordpress,salesforce"

# Last 2 hours only (aggressive)
uv run python -m src.cli --hours 2 --min-lpa 15 --exclude "php,wordpress"
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
