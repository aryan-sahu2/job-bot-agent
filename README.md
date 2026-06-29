# Job Link Aggregator + Smart Filter

Searches multiple job boards, scores relevance with a local LLM (Ollama), and helps you apply via a Tampermonkey userscript that runs in your real browser.

## Components

- **`src/cli.py`** — Scrapes LinkedIn, Indeed, Wellfound, Greenhouse, Lever, Breezy, Recruitee, Workable, SmartRecruiters for jobs matching your config. Scores relevance via Ollama.
- **`src/server.py`** — Local FastAPI server on `:8765` that serves your profile, latest jobs, and generates cover letters via Ollama.
- **`jobbot-assistant.user.js`** — Tampermonkey userscript that injects a floating panel on job application pages (Greenhouse, Lever, Workday, LinkedIn, Indeed, and more). Fills profile fields and cover letters in one click.

## Quick Start

```bash
# Install
uv sync --all-extras

# Ensure Ollama is running
ollama serve

# 1. Update resume.txt with your profile (first line = your name)
# 2. First run — creates config.json automatically
uv run python -m src.cli

# 3. Edit config.json with your preferences
# 4. Run again → jobs appear in output/
uv run python -m src.cli
```

## Apply Workflow

```bash
# 1. Start the local server (leave running in a terminal tab)
uv run python src/server.py

# 2. Install the Tampermonkey userscript:
#    - Install Tampermonkey extension in your browser
#    - Click Tampermonkey → "Create a new script"
#    - Delete the default template, paste jobbot-assistant.user.js contents, save (Ctrl+S)

# 3. Open any job URL from output/jobs_to_apply/*.txt

# 4. The JobBot panel appears bottom-right. Click:
#    "Fill Profile" → fills name, email, phone
#    "Generate Cover Letter" → scrapes job description, generates tailored letter via Ollama
#    Upload your resume manually, review, and submit
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

## Browse Jobs in Browser

With the server running, open `http://127.0.0.1:8765/jobs-view` to see the latest scored jobs in a clean HTML table.

## Keyboard Shortcut

On any job application page, press `Ctrl+Shift+J` to toggle the JobBot panel visibility.

## Why This Works

- **Zero bot detection** — you're in your real browser with real cookies
- **Platform-aware** — dedicated selectors for Greenhouse, Lever, Workday, LinkedIn, Indeed, Breezy, Recruitee, Workable, SmartRecruiters, Ashby
- **Graceful fallback** — unknown sites still work via label/placeholder heuristics
- **Local LLM** — cover letters use your Ollama model; no API keys, no data leaves your machine
- **Human-in-the-loop** — you review every application before it goes out
- **Simple scripts, not complex architecture**
- **Resilient** — skips errors, continues
