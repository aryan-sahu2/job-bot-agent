"""
JobBot Assistant Server
Run: uv run python -m src.server
"""

import json
import re
import sys
from pathlib import Path

# Allow `python src/server.py` / `python -m src.server`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    name = lines[0] if lines else "Applicant"
    email = next((line for line in lines if "@" in line and "." in line.split("@")[-1]), "")
    
    # Better phone detection
    phone = ""
    for line in lines:
        if "@" in line:
            continue
        digits = ''.join(c for c in line if c.isdigit())
        if len(digits) >= 10 and len(digits) <= 15:
            phone = line
            break
    
    # Extract URLs
    linkedin = ""
    website = ""
    github = ""
    for line in lines:
        if "linkedin.com" in line.lower():
            linkedin = line
        elif "github.com" in line.lower() or "gitlab.com" in line.lower():
            github = line
        elif "://" in line and not linkedin and not website and not github:
            if not any(x in line.lower() for x in ["email", "phone", "tel:", "mailto:"]):
                website = line
    
    # Extract experience years
    years_experience = ""
    for line in lines:
        match = re.search(r'(\d+(?:\.\d+)?)\+?\s*years?', line, re.IGNORECASE)
        if match:
            years_experience = match.group(1)
            break
    
    # Extract current role from structured header
    current_role = "Full Stack Developer"
    for line in lines:
        if line.lower().startswith("role:"):
            current_role = line.split(":", 1)[1].strip()
            break
    
    # Extract notice period
    notice_period = "0"
    for line in lines:
        if "notice" in line.lower() and ("week" in line.lower() or "day" in line.lower() or "month" in line.lower()):
            match = re.search(r'(\d+)', line)
            if match:
                notice_period = match.group(1)
            break
    
    # Extract expected CTC
    expected_ctc = ""
    for line in lines:
        if "expected" in line.lower() and ("ctc" in line.lower() or "lpa" in line.lower() or "salary" in line.lower()):
            expected_ctc = line.split(":", 1)[1].strip() if ":" in line else line
            break
    
    # Extract referral source
    referral_source = ""
    for line in lines:
        if line.lower().startswith("source:"):
            referral_source = line.split(":", 1)[1].strip()
            break
    
    parts = name.split()
    return {
        "name": name,
        "first_name": parts[0] if parts else "",
        "last_name": parts[-1] if len(parts) > 1 else "",
        "email": email,
        "phone": phone,
        "website": website or github,
        "linkedin": linkedin,
        "github": github,
        "yearsExperience": years_experience,
        "currentRole": current_role,
        "noticePeriod": notice_period,
        "expectedCtc": expected_ctc,
        "referralSource": referral_source,
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
            f"<tr>"
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("score", 0)}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">'
            f'<a href="{j["url"]}" target="_blank" style="color:#60a5fa;">{j["title"]}</a></td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("company", "")}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #334155;">{j.get("source", "")}</td>'
            f"</tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>JobBot Jobs</title></head>
<body style="background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:24px;">
<h2>Latest Jobs ({len(jobs)} found)</h2>
<table style="width:100%;border-collapse:collapse;">
<thead><tr style="text-align:left;border-bottom:2px solid #475569;">
<th style="padding:8px;">Score</th><th style="padding:8px;">Title</th>
<th style="padding:8px;">Company</th><th style="padding:8px;">Source</th>
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
        f"Write a cover letter for this job application. "
        f"Write it in the voice of a hands-on engineer, not a marketer or HR person.\n\n"
        f"=== JOB ===\n"
        f"Company: {company}\n"
        f"Role: {job_title}\n"
        f"Description: {description}\n\n"
        f"=== CANDIDATE PROFILE ===\n"
        f"{profile.get('raw', '')[:1200]}\n\n"
        f"=== WRITING RULES ===\n"
        f"1. Be direct and conversational. Write like you're explaining your work to a technical colleague.\n"
        f"2. Lead with something specific you built or fixed, not with 'I am writing to express my enthusiastic interest.'\n"
        f"3. Mention concrete technologies, metrics, or outcomes when possible (e.g., 'reduced load time by 40%', 'migrated a legacy stack to Next.js').\n"
        f"4. No corporate filler words: passionate, results-driven, innovative, dynamic, synergize, leveraging, holistic.\n"
        f"5. No generic self-praise like 'strong problem-solving skills' or 'proven track record.' Show, don't tell.\n"
        f"6. Keep it to 2-3 short paragraphs. No addresses, dates, or 'Dear Hiring Manager.' Just the body.\n"
        f"7. If you don't know something specific, don't make it up. Skip it instead of inventing details.\n"
        f"8. End with a simple, low-pressure close — not 'I look forward to discussing my qualifications further.'\n\n"
        f"=== EXAMPLE TONE ===\n"
        f"Bad: 'I am a passionate and results-driven developer dedicated to innovation.'\n"
        f"Good: 'I spent four hours debugging deployment issues because the alternative was shipping something unreliable.'\n\n"
        f"Bad: 'I bring strong problem-solving skills.'\n"
        f"Good: 'Most of my experience comes from building things, deploying them, breaking them, and then figuring out why they broke.'\n\n"
        f"Now write the cover letter:"
        f"=== EXAMPLE COVER LETTER (this is the style, not the content to copy) ===\n"
        f"I've spent the last three years building and breaking production systems — mostly Next.js frontends, Node APIs, and the infrastructure that holds them together. At Infravue, I migrated a legacy HTML/CSS/Three.js stack to Next.js because the old codebase was becoming unmaintainable. Cut maintenance overhead by about 40% and got 3D animations running smoother in the process.\n\n"
        f"Before that, I built a job discovery platform from scratch at Kangagigs — React, Node, PostgreSQL, deployed on AWS EC2 with Nginx and PM2. Scaled it to 500 users, which isn't massive, but I owned every part of it from schema design to server config. I tend to work end-to-end, and I prefer shipping over meetings.\n\n"
        f"Your stack and the scope of this role look like a good fit for how I work. Happy to walk through any of the above in more detail.\n\n"
    )

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout) as client:
            r = await client.post(
                config.llm_api,
                json={
                    "model": config.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "top_p": 0.9,
                    }
                },
            )
            text = r.json().get("response", "").strip()
            return {"cover_letter": text}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8765, reload=False, log_level="info")

