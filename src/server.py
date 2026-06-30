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
    
    try:
        data = json.loads(RESUME_PATH.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in {RESUME_PATH}: {str(e)}"}
    
    # Ensure all expected keys exist with fallbacks
    profile = {
        "name": data.get("name", "Applicant"),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "location": data.get("location", ""),
        "current_role": data.get("current_role", ""),
        "years_experience": data.get("years_experience", ""),
        "linkedin": data.get("linkedin", ""),
        "github": data.get("github", ""),
        "portfolio": data.get("portfolio", ""),
        "website": data.get("portfolio", "") or data.get("github", ""),  # alias for extension
        "notice_period_weeks": data.get("notice_period_weeks", ""),
        "expected_ctc": data.get("expected_ctc", ""),
        "expected_salary_usd_monthly": data.get("expected_salary_usd_monthly", ""),
        "referral_source": data.get("referral_source", ""),
        "custom_answers": data.get("custom_answers", {}),
        "raw": data.get("raw_bio", "") or json.dumps(data, indent=2),
    }
    
    return profile

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
        f"=== OUTPUT RULES ===\n"
        f"1. Output ONLY the cover letter body. No preamble like 'Here is a cover letter' or 'Okay, here is...'.\n"
        f"2. Do not wrap the output in markdown code blocks.\n"
        f"3. Start directly with the first sentence of the letter.\n"
        f"4. Do not include a signature or closing like 'Best regards'.\n\n"
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
                        "temperature": 0.45,
                        "top_p": 0.9,
                    }
                },
            )
            text = r.json().get("response", "").strip()
            return {"cover_letter": text}
    except Exception as e:
        return {"error": str(e)}


@app.post("/answer-question")
async def answer_question(payload: dict):
    profile = payload.get("profile", {})
    question = payload.get("question", "")
    q_type = payload.get("question_type", "general")

    raw = profile.get("raw_bio", "") or profile.get("raw", "")
    expected_ctc = profile.get("expected_ctc", "")
    notice = profile.get("notice_period_weeks", "")
    current_role = profile.get("current_role", "")
    years = profile.get("years_experience", "")
    name = profile.get("name", "the applicant")

    # Pre-computed fast answers (avoid LLM call)
    if q_type == "salary" and expected_ctc:
        return {"answer": expected_ctc}
    if q_type == "availability" and notice:
        return {"answer": "Immediate" if notice in ("0", 0, "0 weeks") else f"{notice} weeks"}

    prompt = f"""You are {name}, a practical engineer answering a job application question. 
Write like you talk to a colleague. No corporate buzzwords.

Question: {question}

Your background:
{raw[:1500]}

Current role: {current_role}
Years of experience: {years}
Expected CTC: {expected_ctc}
Notice period: {notice}

Rules:
- Answer naturally and directly. No fluff.
- Don't use: passionate, results-driven, innovative, dynamic, leveraging, holistic, synergy, proactive.
- Stick to facts from your background. Don't invent experience.
- If the question asks for a word count, respect it.
- If it's about salary, state your range clearly.
- If it's about availability, be direct.
- Write only the answer text. No preamble like "Here is my answer:"""

    try:
        async with httpx.AsyncClient(timeout=config.llm_timeout) as client:
            r = await client.post(
                config.llm_api,
                json={
                    "model": config.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.4, "top_p": 0.9}
                },
            )
            text = r.json().get("response", "").strip()
            # Strip any wrapping quotes or markdown
            text = re.sub(r'^["\']{1,2}|["\']{1,2}$', '', text)
            text = re.sub(r'^```\w*\n?|\n?```$', '', text)
            return {"answer": text}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8765, reload=False, log_level="info")

