# AGENTS.md

# Job Link Aggregator + Smart Filter

Replaces complex Playwright automation with a local FastAPI server + Tampermonkey userscript that runs in your real browser.

## Components

### `src/aggregator.py`
- Searches LinkedIn, Indeed, Wellfound, Greenhouse, Lever, Breezy, Recruitee, Workable, SmartRecruiters
- Scores relevance using a local LLM (Ollama)
- Outputs `output/jobs_found_*.json` and `output/jobs_to_apply_*.txt`

### `src/server.py`
- Local FastAPI server on `127.0.0.1:8765`
- Serves `GET /profile` — parses resume.txt into name, email, phone
- Serves `GET /jobs` — latest aggregated jobs
- Serves `GET /jobs-view` — HTML page to browse jobs
- Proxies `POST /cover-letter` — generates tailored cover letters via Ollama

### `jobbot-assistant.user.js`
- Tampermonkey userscript that runs on any job application page
- Platform-specific selectors for Greenhouse, Lever, Workday, LinkedIn, Indeed, Breezy, Recruitee, Workable, SmartRecruiters, Ashby
- Generic heuristic fallback for unknown sites
- "Fill Profile" — auto-fills name, email, phone
- "Generate Cover Letter" — scrapes job description, generates via Ollama, pastes into form
- Keyboard shortcut: `Ctrl+Shift+J` to toggle panel

## Workflow

```bash
# 1. Update resume.txt with your profile (first line = name)
# 2. Find jobs
uv run python -m src.cli

# 3. Start the server (leave running)
uv run python src/server.py

# 4. Install jobbot-assistant.user.js in Tampermonkey
# 5. Open job URLs from output/jobs_to_apply/*.txt
# 6. Click "Fill All" — then upload resume manually, review, and submit
```

## Setup

```bash
uv sync --all-extras
ollama serve  # Ensure Ollama is running
```

## Principles

1. Human approval before every submission
2. Local-first (Ollama, no cloud APIs)
3. Zero bot detection — runs in your real browser with real cookies
4. Simple scripts, not complex architecture
5. Resilient — skips errors, continues

## Key Conventions

- `resume.txt` — first line is your name, contains email/phone and full profile text
- `config.json` — single source of truth for search config; CLI flags override for a single run
- `output/jobs_found_*.json` — full job data with relevance scores
- `output/jobs_to_apply_*.txt` — one URL per line for the application step
