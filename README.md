# Job Link Aggregator + Smart Filter

Searches multiple job boards, scores relevance with a local LLM (Ollama), and helps you apply via a Tampermonkey userscript that runs in your real browser.

## Components

| Component | What it does |
|---|---|
| **`src/cli.py`** (Aggregator) | Scrapes LinkedIn, Indeed, Wellfound, Greenhouse, Lever, and other boards for jobs matching your config. Sends each description + your resume to Ollama for relevance scoring. Filters, deduplicates, and saves results. |
| **`src/server.py`** (Local API) | FastAPI server on `:8765`. Serves your profile, latest jobs, and generates cover letters via Ollama. Must be running for the extension to work. |
| **`jobbot-extension/content.js`** (Extension) | Tampermonkey userscript that injects a floating panel on job application pages. Fills profile fields and generates cover letters in one click. |

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

## What Each Command Does

### `uv run python -m src.cli` — The Aggregator

Scrapes LinkedIn, Indeed, Wellfound, and any Greenhouse/Lever/etc. boards you configured in `config.json`. Sends each job description + your `resume.txt` to your local Ollama LLM for scoring. Filters out jobs below score 20, excludes blacklisted keywords, filters by salary/hours/startup preferences, and deduplicates by URL.

Saves two files:
- `output/jobs_found_*.json` — full job data with scores and reasons
- `output/jobs_to_apply_*.txt` — plain list of URLs to open

This is purely for discovery. If you already know which jobs to apply to, you can skip it entirely.

### `uv run python src/server.py` — The Local API

Starts a FastAPI web server on `http://127.0.0.1:8765`. Exposes three endpoints the browser extension talks to:

| Endpoint | Purpose |
|---|---|
| `GET /profile` | Reads `resume.txt`, parses your name/email/phone |
| `GET /jobs` | Returns the latest aggregated JSON |
| `POST /cover-letter` | Takes job description + your profile, sends to Ollama, returns generated text |

This must be running for the extension buttons to work. If it's off, "Fill Profile" and "Generate Cover Letter" will fail.

### The Extension Panel

The extension injects a floating panel into any job application page:

- **Fill Profile** — fetches `resume.txt` from the server and injects values into form fields
- **Generate Cover Letter** — scrapes the job description from the current page, sends it to the server, which forwards it to Ollama, then returns the text
- **Paste into Form** — injects that text into the cover letter textarea

## Apply Workflow

```bash
# 1. Start the local server (leave running in a terminal tab)
uv run python src/server.py

# 2. Install the Tampermonkey userscript:
#    - Install Tampermonkey extension in your browser
#    - Click Tampermonkey → "Create a new script"
    #    - Delete the default template, paste the content of jobbot-extension/content.js, save (Ctrl+S)

# 3. Open any job URL from output/jobs_to_apply/*.txt

# 4. The JobBot panel appears bottom-right. Click:
#    "Fill Profile" → fills name, email, phone
#    "Generate Cover Letter" → scrapes job description, generates tailored letter via Ollama
#    Upload your resume manually, review, and submit
```

## What Depends on What

| Step | Required by | Can skip if... |
|---|---|---|
| Aggregator (`src.cli`) | Nothing (optional) | You already know which jobs to apply to, or you're browsing job boards manually |
| Server (`src.server.py`) | Extension buttons (Fill Profile, Generate Cover Letter) | You only want the raw job list from the aggregator, or you plan to apply manually without auto-fill |
| Extension | The server must be running | You can apply manually without the extension. The extension is just a convenience layer |

## Real Scenarios

| Scenario | What to run |
|---|---|
| **Full workflow (recommended)** | Run aggregator → start server → open URLs from `jobs_to_apply_*.txt` → use extension |
| **I already have job tabs open** | Just start the server. Skip the aggregator. Use the extension on any job page |
| **I just want a curated list** | Just run the aggregator. Open the JSON or `jobs-view` in browser. Apply manually |
| **I want to apply on a job board the aggregator didn't scrape** | Start the server. Navigate there manually. The extension works on any page |

## The Only Hard Rule

The server must be running for the extension features to work. The extension is a dumb client — it doesn't talk to Ollama directly. It talks to your local server (`127.0.0.1:8765`), and the server talks to Ollama. Everything else is optional.

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
