# Job Link Aggregator + Smart Filter

Searches 9 job sources (LinkedIn, Indeed, Wellfound, Greenhouse, Lever, Breezy, Recruitee, Workable, SmartRecruiters), scores relevance with a local LLM (Ollama), and helps you apply via a Tampermonkey userscript or Chrome extension.

## Requirements

- **Python >= 3.12**
- **Ollama** running locally (`ollama serve`)
- **uv** package manager

## Setup

```bash
uv sync --all-extras
ollama serve
```

## Project Structure

```
├── src/
│   ├── cli.py                           # CLI entry point (argparse, 98 lines)
│   ├── config.py                        # SearchConfig dataclass + loader
│   ├── models.py                        # JobListing dataclass + parser utils
│   ├── aggregator.py                    # Orchestration: scrape, dedup, filter, score, save
│   ├── server.py                        # FastAPI server on :8765
│   ├── llm.py                           # Ollama integration + relevance scoring
│   └── sources/
│       ├── linkedin.py                  # LinkedIn scraper
│       ├── indeed.py                    # Indeed scraper (curl_cffi)
│       ├── wellfound.py                 # Wellfound scraper (curl_cffi)
│       ├── greenhouse.py                # Greenhouse API
│       ├── lever.py                     # Lever API
│       ├── breezy.py                    # Breezy API
│       ├── recruitee.py                 # Recruitee API
│       ├── workable.py                  # Workable API
│       └── smartrecruiters.py           # SmartRecruiters API
├── jobbot-extension/
│   ├── content.js                       # Tampermonkey userscript / Chrome extension
│   └── manifest.json                    # Chrome extension manifest v3
├── resume.json                          # Your structured profile (primary)
├── resume.txt                           # Legacy plain-text resume (fallback)
├── config.json                          # Single source of truth for search config
└── output/
    ├── jobs_found/                      # Full job data with scores (JSON)
    └── jobs_to_apply/                   # URLs to open (TXT)
```

## Commands

### `uv run python -m src.cli` — Aggregator

Scrapes all configured job sources in parallel. Sends each job description + your resume to Ollama for relevance scoring. Filters, deduplicates, and saves results.

| Flag | Short | Description |
|------|-------|-------------|
| `--config` | `-c` | Path to config JSON (default: `config.json`) |
| `--keywords` | `-k` | Job search keywords |
| `--location` | `-l` | Location (e.g., "Remote", "San Francisco") |
| `--min-salary` | | Minimum salary in USD |
| `--min-lpa` | | Minimum salary in LPA (Indian market) |
| `--experience` | `-e` | Experience level: `entry`, `mid`, `senior`, `staff` |
| `--exclude` | | Comma-separated keywords to exclude |
| `--time-filter` | | LinkedIn time filter code (e.g., `r86400` = 24h) |
| `--hours` | | Only jobs posted within last N hours |
| `--startup` | | Only startup jobs (flag) |
| `--remote` / `--no-remote` | | Remote only toggle (flag) |

Saves two timestamped files:
- `output/jobs_found/jobs_found_{timestamp}.json` — full job data with scores
- `output/jobs_to_apply/jobs_to_apply_{timestamp}.txt` — one URL per line

### `uv run python src/server.py` — Local API

FastAPI server on `http://127.0.0.1:8765`. Must be running for extension features to work.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /` | GET | Health check |
| `GET /profile` | GET | Returns structured profile from `resume.json` |
| `GET /jobs` | GET | Returns latest aggregated jobs |
| `GET /jobs-view` | GET | HTML table of latest jobs (dark theme) |
| `POST /cover-letter` | POST | Generates tailored cover letter via Ollama |
| `POST /answer-question` | POST | Answers custom application questions via Ollama |
| `POST /expand-answer` | POST | Expands a short answer to a target word count |

### The Extension Panel

Install via **Tampermonkey** (open `jobbot-extension/content.js` and copy into a new script) or as a **Chrome extension** (load `jobbot-extension/` unpacked).

The panel injects a floating panel (bottom-right) on any job application page:
- **Fill Profile** — auto-fills name, email, phone, and other fields
- **Generate Cover Letter** — scrapes the job description, generates via Ollama, displays with word count
- **Paste into Form** — injects cover letter into the form's textarea
- **Copy to clipboard** button
- **Collapse/Expand** toggle (remembers state via `sessionStorage`)
- **Server status indicator** (green/red dot)

Smart heuristic field detection — no hardcoded selectors. Works on Greenhouse, Lever, Workday, LinkedIn, Indeed, Breezy, Recruitee, Workable, SmartRecruiters, Ashby, and unknown sites via label/placeholder heuristics.

**Keyboard shortcut:** `Ctrl+Shift+K` (or `Cmd+Shift+K` on Mac) to toggle panel.

## Resume Format (`resume.json`)

The server reads `resume.json` at the project root. Full schema:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Full name |
| `first_name` | string | First name |
| `last_name` | string | Last name |
| `email` | string | Email address |
| `phone` | string | Phone number |
| `location` | string | City, State/Country |
| `current_role` | string | Current job title |
| `years_experience` | string | Years of experience |
| `linkedin` | string | LinkedIn profile URL |
| `github` | string | GitHub profile URL |
| `portfolio` | string | Portfolio/website URL |
| `website` | string | Additional website URL |
| `notice_period_weeks` | string | Notice period in weeks |
| `expected_ctc` | string | Expected CTC (Indian market) |
| `expected_salary_usd_monthly` | string | Expected monthly salary (USD) |
| `expected_salary_usd_yearly` | string | Expected yearly salary (USD) |
| `referral_source` | string | How you found the job |
| `skills` | string | Comma-separated skills |
| `custom_answers` | object | Pre-written answers for common questions |
| `custom_answers.introduction` | string | "Tell me about yourself" answer |
| `custom_answers.motivation` | string | "Why this company?" answer |
| `custom_answers.cover_letter` | string | Pre-written cover letter |
| `raw_bio` | string | Full biography text |

A plain-text `resume.txt` fallback is supported (first line = name, contains email/phone).

## Configuration

Edit `config.json` at the project root.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `keywords` | string | `"Full Stack Engineer"` | Search keywords |
| `location` | string | `"Remote"` | Location |
| `min_salary` | int / null | `null` | Minimum salary in USD |
| `min_salary_lakhs` | float | `15.0` | Minimum salary in LPA |
| `remote_only` | bool | `true` | Only remote jobs |
| `experience_level` | string | `"mid"` | `entry`, `mid`, `senior`, or `staff` |
| `exclude_keywords` | list | `[php, wordpress, salesforce, drupal]` | Keywords to exclude |
| `hours_since_posted` | int | `4` | Recency filter (hours) |
| `startup_only` | bool | `false` | Only startup jobs |
| `linkedin_time_filter` | string | `"r86400"` | LinkedIn time filter code |
| `linkedin_remote_filter` | string | `"2"` | LinkedIn remote filter code |
| `linkedin_distance` | string | `"25"` | LinkedIn distance filter (miles) |
| `greenhouse_boards` | list | `[]` | Company slugs for Greenhouse ATS |
| `lever_slugs` | list | `[]` | Company slugs for Lever ATS |
| `breezy_boards` | list | `[]` | Company slugs for Breezy HR |
| `recruitee_boards` | list | `[]` | Company slugs for Recruitee |
| `workable_accounts` | list | `[]` | Account names for Workable |
| `smartrecruiters_companies` | list | `[]` | Company IDs for SmartRecruiters |
| `max_jobs_per_source` | int | `15` | Max jobs to scrape per source |
| `llm_api` | string | `"http://localhost:11434/api/generate"` | Ollama API endpoint |
| `llm_model` | string | `"gemma3"` | Ollama model name |
| `llm_timeout` | int | `90` | LLM request timeout (seconds) |
| `output_dir` | string | `"output"` | Output directory |
| `resume_path` | string | `"resume.txt"` | Path to resume/profile file |

## Why This Works

- **Zero bot detection** — you're in your real browser with real cookies
- **9 job sources** — LinkedIn, Indeed, Wellfound, Greenhouse, Lever, Breezy, Recruitee, Workable, SmartRecruiters
- **Platform-aware + graceful fallback** — dedicated detection for major ATS platforms; unknown sites still work via heuristics
- **Local LLM** — cover letters and relevance scoring use your Ollama model; no API keys, no data leaves your machine
- **Human-in-the-loop** — you review every application before it goes out
- **Simple scripts, not complex architecture**
- **Resilient** — skips errors, continues
