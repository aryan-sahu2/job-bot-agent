"""
JobBot Assistant Server
Run: uv run python -m src.server
"""

import json
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
    email = next((line for line in lines if "@" in line), "")
    
    # Better phone detection: must contain digits AND look like a phone number
    phone = ""
    for line in lines:
        if "@" in line:
            continue  # skip emails
        digits = ''.join(c for c in line if c.isdigit())
        if len(digits) >= 10 and len(digits) <= 15:
            # Looks like a phone number (10-15 digits)
            phone = line
            break
    
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
        f"You are {profile.get('name', 'the applicant')}. Write a brief, professional cover letter "
        f"for this job:\n\nCompany: {company}\nRole: {job_title}\n"
        f"Description: {description}\n\nYour profile:\n{profile.get('raw', '')[:1000]}\n\n"
        f"Write 2-3 short paragraphs. Be specific, not generic. "
        f"Mention relevant skills and experience. "
        f"Do not include addresses, dates, or salutations "
        f"like 'Dear Hiring Manager'. Just the body paragraphs."
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
    uvicorn.run("src.server:app", host="0.0.0.0", port=8765, reload=False, log_level="info")

