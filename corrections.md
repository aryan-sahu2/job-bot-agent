Here is how (browser assistant) fits into your existing codebase. It replaces the brittle Playwright automation with a local API server + a Tampermonkey userscript that runs inside your real browser. You manually click a job URL, the userscript detects the application form, and fills it from your local profile in one click.
How it works
src/server.py — a tiny local FastAPI server on localhost:8765. It reads your resume.txt, serves your latest aggregated jobs, and proxies cover-letter requests to your local Ollama instance.
jobbot-assistant.user.js — a Tampermonkey userscript that injects a floating “JobBot” panel onto any job application page (Greenhouse, Lever, Workday, Breezy, etc.).
Workflow:
Run uv run python src/server.py in one terminal.
Install the userscript in your browser (Tampermonkey).
Click any job URL from your generated list.
Hit Fill Profile → it auto-fills name, email, phone.
Hit Generate Cover Letter → it scrapes the job description, asks your local LLM for a tailored letter, and pastes it into the form.
You upload your resume manually (browsers block file-input automation for security) and click Submit.
What to keep
Table
File / Directory	Why
src/aggregator.py	Still scrapes and scores jobs.
src/cli.py	Still runs the aggregator.
src/config.py	Still loads config.
src/llm.py	Still used by aggregator for scoring; server reuses the same logic.
src/models.py	Still used everywhere.
src/sources/*	All sources remain.
config.json	Add new keys for ATS boards if you want, but existing keys stay.
resume.txt	Now read by the server on every request.
pyproject.toml	Keep, but remove playwright and add fastapi + uvicorn.
What to remove
Table
File / Item	Why
src/apply.py	Delete entirely. Playwright automation is replaced by the browser userscript.
playwright dependency	Remove from pyproject.toml / uv.lock. No longer needed.
screenshots/ directory	No longer generated; you can delete old screenshots.
What to add
Table
File	Purpose
src/server.py	Local API server (profile, jobs, cover-letter proxy).
jobbot-assistant.user.js	Tampermonkey userscript (place in repo root for reference).
fastapi, uvicorn	New Python dependencies.
Dependency update
bash
# Remove the old browser automation stack
uv remove playwright

# Add the local server stack
uv add fastapi uvicorn
1. src/server.py (new file)
Python
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from src.config import load_config

app = FastAPI(title="JobBot Assistant")

# Allow the userscript to call from any job-board domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()
RESUME_PATH = Path(config.resume_path)
OUTPUT_DIR = Path(config.output_dir)


def _latest_jobs_path() -> Path | None:
    d = OUTPUT_DIR / "jobs_found"
    if not d.exists():
        return None
    files = sorted(d.glob("jobs_found_*.json"), reverse=True)
    return files[0] if files else None


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/profile")
def get_profile():
    if not RESUME_PATH.exists():
        return {"error": f"{RESUME_PATH} not found"}
    raw = RESUME_PATH.read_text()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    name = lines[0] if lines else "Applicant"
    email = next((l for l in lines if "@" in l), "")
    phone = next((l for l in lines if any(c.isdigit() for c in l) and len(l) > 9), "")
    parts = name.split()
    return {
        "name": name,
        "first_name": parts[0] if parts else "",
        "last_name": parts[-1] if len(parts) > 1 else "",
        "email": email,
        "phone": phone,
        "raw": raw,
    }


@app.get("/jobs")
def get_jobs():
    p = _latest_jobs_path()
    if not p:
        return []
    return json.loads(p.read_text())


@app.post("/cover-letter")
async def cover_letter(payload: dict):
    profile = payload.get("profile", {})
    job_title = payload.get("job_title", "")
    company = payload.get("company", "")
    description = payload.get("description", "")[:1500]

    prompt = (
        f"You are {profile.get('name', 'the applicant')}. Write a brief, professional cover letter "
        f"for this job:\n\nCompany: {company}\nRole: {job_title}\n"
        f"Description: {description}\n\nYour profile:\n{profile.get('raw', '')[:1000]}\n\n"
        f"Write 2-3 short paragraphs. Be specific, not generic. Mention relevant skills and experience. "
        f"Do not include addresses or dates. Just the body paragraphs."
    )

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout) as client:
            r = await client.post(
                config.llm_api,
                json={"model": config.llm_model, "prompt": prompt, "stream": False},
            )
            text = r.json().get("response", "").strip()
            return {"cover_letter": text}
    except Exception as e:
        return {"error": str(e)}


def main():
    uvicorn.run("src.server:app", host="127.0.0.1", port=8765, reload=False, log_level="info")


if __name__ == "__main__":
    main()
2. jobbot-assistant.user.js (new file)
Save this as jobbot-assistant.user.js in your repo root, then install it via Tampermonkey.
JavaScript
// ==UserScript==
// @name         JobBot Assistant
// @namespace    jobbot
// @version      1.0
// @description  Auto-fill job applications using your local JobBot profile
// @author       You
// @match        *://*.greenhouse.io/*
// @match        *://boards.greenhouse.io/*
// @match        *://*.lever.co/*
// @match        *://jobs.lever.co/*
// @match        *://*.workday.com/*
// @match        *://*.myworkdayjobs.com/*
// @match        *://*.breezy.hr/*
// @match        *://*.recruitee.com/*
// @match        *://*.workable.com/*
// @match        *://*.smartrecruiters.com/*
// @match        *://*.ashbyhq.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const SERVER = 'http://127.0.0.1:8765';
    let profileCache = null;

    // --- UI Panel ---
    const panel = document.createElement('div');
    panel.id = 'jobbot-panel';
    panel.innerHTML = `
      <div style="position:fixed;bottom:20px;right:20px;z-index:99999;background:#0f172a;color:#e2e8f0;padding:16px;border-radius:12px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,0.5);width:300px;border:1px solid #334155;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <strong style="font-size:14px;">🤖 JobBot Assistant</strong>
          <button id="jb-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:20px;line-height:1;">×</button>
        </div>
        <div id="jb-status" style="font-size:12px;color:#94a3b8;margin-bottom:12px;min-height:18px;">Checking server...</div>
        <button id="jb-fill" style="width:100%;padding:10px;margin-bottom:8px;background:#10b981;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Fill Profile</button>
        <button id="jb-cover" style="width:100%;padding:10px;margin-bottom:8px;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Generate Cover Letter</button>
        <button id="jb-jobs" style="width:100%;padding:10px;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Open Latest Jobs</button>
        <div id="jb-extra" style="margin-top:10px;"></div>
      </div>
    `;
    document.body.appendChild(panel);

    const statusEl = document.getElementById('jb-status');
    const extraEl = document.getElementById('jb-extra');

    function setStatus(msg) {
        statusEl.textContent = msg;
    }

    document.getElementById('jb-close').onclick = () => {
        document.getElementById('jobbot-panel').style.display = 'none';
    };

    // --- Server health check ---
    fetch(`${SERVER}/`).then(r => r.json()).then(() => {
        setStatus('Connected — ready to assist');
    }).catch(() => {
        setStatus('⚠️ Server offline. Run: uv run python src/server.py');
    });

    // --- Field helpers ---
    function getLabel(el) {
        if (el.id) {
            const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (lbl) return lbl.innerText;
        }
        const parent = el.closest('label');
        if (parent) return parent.innerText;
        const ariaId = el.getAttribute('aria-labelledby');
        if (ariaId) {
            const lbl = document.getElementById(ariaId);
            if (lbl) return lbl.innerText;
        }
        return el.getAttribute('aria-label') || '';
    }

    function findField(keywords) {
        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');
        for (const el of inputs) {
            const text = `${getLabel(el)} ${el.placeholder || ''} ${el.name || ''} ${el.id || ''}`.toLowerCase();
            if (keywords.some(k => text.includes(k))) return el;
        }
        return null;
    }

    function setField(el, value) {
        if (!el) return false;
        if (el.tagName === 'SELECT') {
            const opts = Array.from(el.options);
            const yesOpt = opts.find(o => /yes|agree|confirm|accept/i.test(o.text));
            if (yesOpt) el.value = yesOpt.value;
            else if (opts.length > 1) el.value = opts[1].value;
        } else {
            el.focus();
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.blur();
        }
        return true;
    }

    // --- Actions ---
    async function loadProfile() {
        if (profileCache) return profileCache;
        const res = await fetch(`${SERVER}/profile`);
        profileCache = await res.json();
        if (profileCache.error) throw new Error(profileCache.error);
        return profileCache;
    }

    document.getElementById('jb-fill').onclick = async () => {
        try {
            setStatus('Loading profile...');
            const p = await loadProfile();
            let filled = 0;

            if (setField(findField(['first name', 'given name', 'fname']), p.first_name)) filled++;
            if (setField(findField(['last name', 'surname', 'lname']), p.last_name)) filled++;
            if (!filled && setField(findField(['full name', 'name']), p.name)) filled++;
            if (setField(findField(['email', 'e-mail']), p.email)) filled++;
            if (setField(findField(['phone', 'mobile', 'cell', 'tel']), p.phone)) filled++;

            setStatus(`Filled ${filled} fields. Resume upload must be done manually.`);
        } catch (e) {
            setStatus('Error: ' + e.message);
        }
    };

    function extractJobDetails() {
        const h1 = document.querySelector('h1');
        const title = h1 ? h1.innerText.trim() : '';
        let company = '';
        const og = document.querySelector('meta[property="og:site_name"]');
        if (og) company = og.content;
        else {
            const m = window.location.hostname.match(/^([^\.]+)\./);
            if (m) company = m[1];
        }
        let desc = '';
        const selectors = [
            '[class*="description"]', '[class*="job-description"]', '#jobDescriptionText',
            '[data-testid*="description"]', '.section.page-centered', '[class*="posting"]'
        ];
        for (const s of selectors) {
            const el = document.querySelector(s);
            if (el) { desc = el.innerText.substring(0, 2000); break; }
        }
        return { job_title: title, company, description: desc };
    }

    document.getElementById('jb-cover').onclick = async () => {
        try {
            setStatus('Generating cover letter...');
            const p = await loadProfile();
            const job = extractJobDetails();
            const res = await fetch(`${SERVER}/cover-letter`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profile: p, ...job })
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);

            const el = findField(['cover letter', 'additional', 'message', 'why', 'tell us', 'comments', 'note']);
            if (el) {
                setField(el, data.cover_letter);
                setStatus('Cover letter filled.');
            } else {
                extraEl.innerHTML = `<textarea style="width:100%;height:120px;margin-top:8px;font-size:12px;">${data.cover_letter.replace(/</g,'&lt;')}</textarea>`;
                setStatus('No cover letter field found. Copied above — paste manually.');
            }
        } catch (e) {
            setStatus('Error: ' + e.message);
        }
    };

    document.getElementById('jb-jobs').onclick = async () => {
        try {
            const res = await fetch(`${SERVER}/jobs`);
            const jobs = await res.json();
            if (!jobs.length) {
                setStatus('No jobs found. Run aggregator first.');
                return;
            }
            const list = jobs.slice(0, 10).map(j =>
                `<li style="margin-bottom:6px;"><a href="${j.url}" target="_blank" style="color:#60a5fa;">${j.title} @ ${j.company}</a></li>`
            ).join('');
            extraEl.innerHTML = `<ul style="padding-left:16px;font-size:12px;max-height:200px;overflow-y:auto;">${list}</ul>`;
            setStatus(`Showing ${Math.min(jobs.length, 10)} jobs.`);
        } catch (e) {
            setStatus('Error loading jobs.');
        }
    };
})();
How to use it
Update dependencies
bash
uv remove playwright
uv add fastapi uvicorn
Delete the old apply bot
bash
rm src/apply.py
rm -rf screenshots/
Start the local server (leave it running in a terminal tab)
bash
uv run python src/server.py
Install the userscript
Install the Tampermonkey extension in your browser.
Click Tampermonkey → “Create a new script”.
Delete the default template, paste the entire contents of jobbot-assistant.user.js, and save (Ctrl+S).
Run your workflow
uv run python src/cli.py (or aggregator.py) to generate jobs as usual.
Open any job URL from output/jobs_to_apply/*.txt.
The green JobBot panel appears in the bottom-right.
Click Fill Profile → Generate Cover Letter → upload resume manually → hit Submit.



Here is the definitive, production-ready implementation. This replaces the brittle Playwright automation with a local FastAPI server + Tampermonkey userscript that runs inside your real browser.
What to delete
bash
rm src/apply.py
rm -rf screenshots/
rm src/sources/naukri.py      # if you still have it
rm src/sources/remoteok.py    # if you still have it
rm src/sources/weworkremotely.py  # if you still have it
Dependency changes
bash
uv remove playwright
uv add fastapi uvicorn
1. src/server.py — Local API backend
Create this file. It serves your profile, latest jobs, and proxies cover-letter requests to your local Ollama.
Python
"""
JobBot Assistant Server
Run: uv run python src/server.py
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import httpx

from src.config import load_config

app = FastAPI(title="JobBot Assistant")

# CORS: userscript calls from arbitrary job-board domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

config = load_config()
RESUME_PATH = Path(config.resume_path)
OUTPUT_DIR = Path(config.output_dir)


def _latest_jobs_file() -> Path | None:
    d = OUTPUT_DIR / "jobs_found"
    if not d.exists():
        return None
    files = sorted(d.glob("jobs_found_*.json"), reverse=True)
    return files[0] if files else None


@app.get("/")
def health():
    return {"status": "ok", "profile": RESUME_PATH.exists()}


@app.get("/profile")
def get_profile():
    if not RESUME_PATH.exists():
        return {"error": f"{RESUME_PATH} not found"}
    raw = RESUME_PATH.read_text()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    name = lines[0] if lines else "Applicant"
    email = next((l for l in lines if "@" in l), "")
    phone = next((l for l in lines if any(c.isdigit() for c in l) and len(l) > 9), "")
    parts = name.split()
    return {
        "name": name,
        "first_name": parts[0] if parts else "",
        "last_name": parts[-1] if len(parts) > 1 else "",
        "email": email,
        "phone": phone,
        "raw": raw,
    }


@app.get("/jobs")
def get_jobs():
    p = _latest_jobs_file()
    if not p:
        return []
    return json.loads(p.read_text())


@app.get("/jobs-view", response_class=HTMLResponse)
def jobs_view():
    """Simple HTML page so you can browse jobs in a tab."""
    p = _latest_jobs_file()
    if not p:
        return "<h1>No jobs found. Run aggregator first.</h1>"
    jobs = json.loads(p.read_text())
    rows = ""
    for j in jobs[:50]:
        rows += (
            f'<tr>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("score",0)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;"><a href="{j["url"]}" target="_blank" style="color:#60a5fa;">{j["title"]}</a></td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("company","")}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("source","")}</td>'
            f'</tr>'
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>JobBot Jobs</title></head>
<body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px;">
<h2>Latest Jobs ({len(jobs)} found)</h2>
<table style="width:100%;border-collapse:collapse;">
<thead><tr style="text-align:left;border-bottom:2px solid #475569;">
<th style="padding:8px;">Score</th><th style="padding:8px;">Title</th><th style="padding:8px;">Company</th><th style="padding:8px;">Source</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>"""


@app.post("/cover-letter")
async def cover_letter(payload: dict):
    profile = payload.get("profile", {})
    job_title = payload.get("job_title", "")
    company = payload.get("company", "")
    description = payload.get("description", "")[:1800]

    prompt = (
        f"You are {profile.get('name', 'the applicant')}. Write a brief, professional cover letter "
        f"for this job:\n\nCompany: {company}\nRole: {job_title}\n"
        f"Description: {description}\n\nYour profile:\n{profile.get('raw', '')[:1000]}\n\n"
        f"Write 2-3 short paragraphs. Be specific, not generic. Mention relevant skills and experience. "
        f"Do not include addresses, dates, or salutations like 'Dear Hiring Manager'. Just the body paragraphs."
    )

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout) as client:
            r = await client.post(
                config.llm_api,
                json={"model": config.llm_model, "prompt": prompt, "stream": False},
            )
            text = r.json().get("response", "").strip()
            return {"cover_letter": text}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8765, reload=False, log_level="info")
2. jobbot-assistant.user.js — Tampermonkey userscript
Save this as jobbot-assistant.user.js in your repo, then install it via Tampermonkey (Create new script → paste → save).
JavaScript
// ==UserScript==
// @name         JobBot Assistant
// @namespace    jobbot
// @version      2.0
// @description  Auto-fill job applications using your local JobBot profile
// @author       You
// @match        *://*.greenhouse.io/*
// @match        *://boards.greenhouse.io/*
// @match        *://*.lever.co/*
// @match        *://jobs.lever.co/*
// @match        *://*.workday.com/*
// @match        *://*.myworkdayjobs.com/*
// @match        *://*.linkedin.com/*
// @match        *://*.indeed.com/*
// @match        *://*.breezy.hr/*
// @match        *://*.recruitee.com/*
// @match        *://*.workable.com/*
// @match        *://*.smartrecruiters.com/*
// @match        *://*.ashbyhq.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const SERVER = 'http://127.0.0.1:8765';
    let profileCache = null;

    /* ── Platform detection ── */
    function detectPlatform() {
        const h = location.hostname;
        if (h.includes('greenhouse.io')) return 'greenhouse';
        if (h.includes('lever.co')) return 'lever';
        if (h.includes('workday.com') || h.includes('myworkdayjobs.com')) return 'workday';
        if (h.includes('linkedin.com')) return 'linkedin';
        if (h.includes('indeed.com')) return 'indeed';
        if (h.includes('breezy.hr')) return 'breezy';
        if (h.includes('recruitee.com')) return 'recruitee';
        if (h.includes('workable.com')) return 'workable';
        if (h.includes('smartrecruiters.com')) return 'smartrecruiters';
        if (h.includes('ashbyhq.com')) return 'ashby';
        return 'generic';
    }
    const PLATFORM = detectPlatform();

    /* ── Platform-specific selectors ── */
    const SELECTORS = {
        greenhouse: {
            firstName: ['#first_name'],
            lastName: ['#last_name'],
            fullName: [],
            email: ['#email'],
            phone: ['#phone'],
            coverLetter: ['#cover_letter'],
            resume: ['#resume']
        },
        lever: {
            firstName: [],
            lastName: [],
            fullName: ['input[name="name"]'],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="comments"]'],
            resume: ['input[name="resume"]']
        },
        workday: {
            firstName: ['input[data-automation-id="legalNameSection_firstName"]', 'input[autocomplete="given-name"]'],
            lastName: ['input[data-automation-id="legalNameSection_lastName"]', 'input[autocomplete="family-name"]'],
            fullName: [],
            email: ['input[data-automation-id="email"]', 'input[type="email"]'],
            phone: ['input[data-automation-id="phone-number"]'],
            coverLetter: ['textarea[data-automation-id="coverLetter"]'],
            resume: ['input[data-automation-id="resume"]']
        },
        linkedin: {
            firstName: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-firstName'],
            lastName: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-lastName'],
            fullName: [],
            email: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-email'],
            phone: ['#single-line-text-form-component-formElement-urn-li-jobs-applyformcommon-easyApplyFormElement-0-phoneNumber'],
            coverLetter: [],
            resume: []
        },
        indeed: {
            firstName: ['#input-firstName'],
            lastName: ['#input-lastName'],
            fullName: [],
            email: ['#input-email'],
            phone: ['#input-phoneNumber'],
            coverLetter: [],
            resume: []
        },
        breezy: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_resume']
        },
        recruitee: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_cv']
        },
        workable: {
            firstName: ['#candidate_first_name'],
            lastName: ['#candidate_last_name'],
            fullName: [],
            email: ['#candidate_email'],
            phone: ['#candidate_phone'],
            coverLetter: ['#candidate_cover_letter'],
            resume: ['#candidate_resume']
        },
        smartrecruiters: {
            firstName: ['input[name="firstName"]'],
            lastName: ['input[name="lastName"]'],
            fullName: [],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="coverLetter"]'],
            resume: ['input[name="resume"]']
        },
        ashby: {
            firstName: ['input[name="firstName"]'],
            lastName: ['input[name="lastName"]'],
            fullName: [],
            email: ['input[name="email"]'],
            phone: ['input[name="phone"]'],
            coverLetter: ['textarea[name="coverLetter"]'],
            resume: ['input[name="resume"]']
        },
        generic: {
            firstName: [],
            lastName: [],
            fullName: [],
            email: [],
            phone: [],
            coverLetter: [],
            resume: []
        }
    };

    /* ── UI Panel ── */
    const panel = document.createElement('div');
    panel.id = 'jobbot-panel';
    panel.innerHTML = `
      <div style="position:fixed;bottom:20px;right:20px;z-index:99999;background:#0f172a;color:#e2e8f0;padding:16px;border-radius:12px;font-family:system-ui,-apple-system,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,0.5);width:320px;border:1px solid #334155;max-height:90vh;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <strong style="font-size:14px;">🤖 JobBot</strong>
          <div>
            <span id="jb-badge" style="font-size:10px;background:#334155;padding:2px 6px;border-radius:4px;margin-right:6px;text-transform:uppercase;">${PLATFORM}</span>
            <button id="jb-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:18px;line-height:1;">×</button>
          </div>
        </div>
        <div id="jb-status" style="font-size:12px;color:#94a3b8;margin-bottom:12px;min-height:18px;">Checking server...</div>

        <button id="jb-fill" style="width:100%;padding:10px;margin-bottom:8px;background:#10b981;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Fill Profile</button>
        <button id="jb-cover" style="width:100%;padding:10px;margin-bottom:8px;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Generate Cover Letter</button>
        <button id="jb-all" style="width:100%;padding:10px;margin-bottom:8px;background:#8b5cf6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Fill All (Profile + Cover)</button>
        <button id="jb-jobs" style="width:100%;padding:10px;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">Open Latest Jobs</button>

        <div id="jb-extra" style="margin-top:10px;font-size:12px;"></div>
        <div id="jb-warning" style="margin-top:10px;font-size:11px;color:#fbbf24;display:none;"></div>
      </div>
    `;
    document.body.appendChild(panel);

    const $ = id => document.getElementById(id);
    const statusEl = $('jb-status');
    const extraEl = $('jb-extra');
    const warningEl = $('jb-warning');

    function setStatus(msg) { statusEl.textContent = msg; }
    function showWarning(msg) { warningEl.textContent = msg; warningEl.style.display = 'block'; }

    $('jb-close').onclick = () => { panel.style.display = 'none'; };
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'J') {
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }
    });

    /* ── Server health ── */
    fetch(`${SERVER}/`).then(r => r.json()).then(() => {
        setStatus('Connected — ready');
    }).catch(() => {
        setStatus('⚠️ Server offline. Run: uv run python src/server.py');
    });

    /* ── Field helpers ── */
    function getLabel(el) {
        if (el.id) {
            const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (lbl) return lbl.innerText;
        }
        const parent = el.closest('label');
        if (parent) return parent.innerText;
        const ariaId = el.getAttribute('aria-labelledby');
        if (ariaId) {
            const lbl = document.getElementById(ariaId);
            if (lbl) return lbl.innerText;
        }
        return el.getAttribute('aria-label') || '';
    }

    function queryPlatformOrGeneric(type) {
        const sels = SELECTORS[PLATFORM][type] || [];
        for (const s of sels) {
            const el = document.querySelector(s);
            if (el) return el;
        }
        // Fallback: heuristic label/placeholder search
        const keywords = {
            firstName: ['first name', 'given name', 'fname', 'first-name'],
            lastName: ['last name', 'surname', 'lname', 'last-name'],
            fullName: ['full name', 'name', 'your name'],
            email: ['email', 'e-mail'],
            phone: ['phone', 'mobile', 'cell', 'tel'],
            coverLetter: ['cover letter', 'additional', 'message', 'why', 'tell us', 'comments', 'note', 'summary'],
            resume: ['resume', 'cv', 'upload']
        }[type] || [];
        const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');
        for (const el of inputs) {
            const text = `${getLabel(el)} ${el.placeholder || ''} ${el.name || ''} ${el.id || ''}`.toLowerCase();
            if (keywords.some(k => text.includes(k))) return el;
        }
        return null;
    }

    function setField(el, value) {
        if (!el) return false;
        if (el.tagName === 'SELECT') {
            const opts = Array.from(el.options);
            const yesOpt = opts.find(o => /yes|agree|confirm|accept/i.test(o.text));
            if (yesOpt) el.value = yesOpt.value;
            else if (opts.length > 1) el.value = opts[1].value;
        } else {
            el.focus();
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.blur();
        }
        return true;
    }

    /* ── Profile ── */
    async function loadProfile() {
        if (profileCache) return profileCache;
        const res = await fetch(`${SERVER}/profile`);
        profileCache = await res.json();
        if (profileCache.error) throw new Error(profileCache.error);
        return profileCache;
    }

    async function fillProfile() {
        const p = await loadProfile();
        let filled = 0;
        let fn = queryPlatformOrGeneric('firstName');
        let ln = queryPlatformOrGeneric('lastName');
        if (!fn && !ln) {
            const full = queryPlatformOrGeneric('fullName');
            if (full) { setField(full, p.name); filled++; }
        } else {
            if (setField(fn, p.first_name)) filled++;
            if (setField(ln, p.last_name)) filled++;
        }
        if (setField(queryPlatformOrGeneric('email'), p.email)) filled++;
        if (setField(queryPlatformOrGeneric('phone'), p.phone)) filled++;
        return filled;
    }

    $('jb-fill').onclick = async () => {
        try {
            setStatus('Filling profile...');
            const n = await fillProfile();
            setStatus(`Filled ${n} profile fields. Upload resume manually.`);
            const resumeEl = queryPlatformOrGeneric('resume');
            if (resumeEl) showWarning('⚠️ Resume upload must be done manually (browser security).');
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Cover letter ── */
    function extractJobDetails() {
        const h1 = document.querySelector('h1, h2');
        const title = h1 ? h1.innerText.trim() : document.title;
        let company = '';
        const og = document.querySelector('meta[property="og:site_name"]');
        if (og) company = og.content;
        else {
            const m = window.location.hostname.match(/^([^\.]+)\./);
            if (m) company = m[1];
        }
        let desc = '';
        const descSelectors = [
            '[class*="description"]', '[class*="job-description"]', '#jobDescriptionText',
            '[data-testid*="description"]', '.section.page-centered', '[class*="posting"]',
            '[class*="jobDescription"]', '[class*="details"]'
        ];
        for (const s of descSelectors) {
            const el = document.querySelector(s);
            if (el) { desc = el.innerText.substring(0, 2500); break; }
        }
        return { job_title: title, company, description: desc };
    }

    async function fillCoverLetter() {
        const p = await loadProfile();
        const job = extractJobDetails();
        setStatus('Generating cover letter...');
        const res = await fetch(`${SERVER}/cover-letter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile: p, ...job })
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        const el = queryPlatformOrGeneric('coverLetter');
        if (el) {
            setField(el, data.cover_letter);
            return { filled: true, text: data.cover_letter };
        } else {
            return { filled: false, text: data.cover_letter };
        }
    }

    $('jb-cover').onclick = async () => {
        try {
            const result = await fillCoverLetter();
            if (result.filled) {
                setStatus('Cover letter filled.');
            } else {
                extraEl.innerHTML = `<textarea style="width:100%;height:140px;margin-top:8px;font-size:12px;border-radius:4px;padding:8px;">${result.text.replace(/</g,'&lt;')}</textarea>`;
                setStatus('No cover letter field found. Copied above — paste manually.');
            }
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Fill All ── */
    $('jb-all').onclick = async () => {
        try {
            setStatus('Filling profile...');
            const n = await fillProfile();
            setStatus('Generating cover letter...');
            const result = await fillCoverLetter();
            if (result.filled) {
                setStatus(`Filled ${n} fields + cover letter. Review & submit.`);
            } else {
                extraEl.innerHTML = `<textarea style="width:100%;height:140px;margin-top:8px;font-size:12px;border-radius:4px;padding:8px;">${result.text.replace(/</g,'&lt;')}</textarea>`;
                setStatus(`Filled ${n} fields. Cover letter copied above — paste manually.`);
            }
            const resumeEl = queryPlatformOrGeneric('resume');
            if (resumeEl) showWarning('⚠️ Remember to upload your resume manually.');
        } catch (e) { setStatus('Error: ' + e.message); }
    };

    /* ── Open Jobs ── */
    $('jb-jobs').onclick = async () => {
        try {
            const res = await fetch(`${SERVER}/jobs`);
            const jobs = await res.json();
            if (!jobs.length) {
                setStatus('No jobs found. Run aggregator first.');
                return;
            }
            const list = jobs.slice(0, 15).map(j =>
                `<li style="margin-bottom:6px;"><a href="${j.url}" target="_blank" style="color:#60a5fa;text-decoration:none;">${j.title} @ ${j.company}</a> <span style="color:#64748b;">(${j.source})</span></li>`
            ).join('');
            extraEl.innerHTML = `<ul style="padding-left:16px;font-size:12px;max-height:240px;overflow-y:auto;">${list}</ul>`;
            setStatus(`Showing ${Math.min(jobs.length, 15)} jobs.`);
        } catch (e) { setStatus('Error loading jobs.'); }
    };
})();
3. Tiny modifications to existing files
In src/aggregator.py, change the final print inside save_results:
Python
# Replace this:
print("\nNext: uv run python apply.py output/jobs_to_apply/jobs_to_apply_*.txt")

# With this:
print("\nNext steps:")
print("  1. uv run python src/server.py")
print("  2. Install jobbot-assistant.user.js in Tampermonkey")
print("  3. Open job URLs from output/jobs_to_apply/*.txt")
In src/cli.py, change the same final print:
Python
# Replace this:
print("\nNext: uv run python apply.py output/jobs_to_apply/jobs_to_apply_*.txt")

# With this:
print("\nNext steps:")
print("  1. uv run python src/server.py")
print("  2. Install jobbot-assistant.user.js in Tampermonkey")
print("  3. Open job URLs from output/jobs_to_apply/*.txt")
4. Setup & daily workflow
bash
# 1. Update dependencies
uv remove playwright
uv add fastapi uvicorn

# 2. Start the server (leave running)
uv run python src/server.py

# 3. In another terminal, run the aggregator
uv run python src/cli.py

# 4. Open http://127.0.0.1:8765/jobs-view in a browser tab
#    or open individual URLs from output/jobs_to_apply/*.txt

# 5. On any job application page, the JobBot panel appears bottom-right.
#    Click "Fill All", upload your resume manually, review, submit.
Why this is the best version
Zero bot detection — you are in your real browser with real cookies.
Platform-aware — Greenhouse, Lever, Workday, LinkedIn, Indeed, Breezy, Recruitee, Workable, SmartRecruiters, Ashby all have dedicated selectors.
Graceful fallback — unknown sites still work via label/placeholder heuristics.
Local LLM — cover letters still use your gemma3 via Ollama; no API keys, no data leaves your machine.
No maintenance nightmare — if a site changes its CSS, the generic label fallback still works; you only need to update the specific selector list.
Keyboard shortcut — Ctrl+Shift+J toggles the panel if you need to hide it.
That is the complete, final implementation.