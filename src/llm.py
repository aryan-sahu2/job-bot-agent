import json
import re

import httpx

from src.config import SearchConfig
from src.models import JobListing, parse_salary


async def ask_llm(prompt: str, model: str = "gemma3", timeout: int = 90) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            return r.json().get("response", "").strip()
    except Exception as e:
        print(f"    LLM request failed: {e}")
        return ""


async def evaluate_job(
    job: JobListing, profile: str, config: SearchConfig
) -> tuple[float, str, str | None]:
    title_company = f"{job.title} {job.company}".lower()
    desc_lower = job.description.lower()
    combined = f"{title_company} {desc_lower} {job.location.lower()}"

    score = 0.0
    reasons = []

    # Title matches are strong signal (×20), description/location are weak (×5)
    kw_clean = config.keywords.lower().replace("-", " ")
    keyword_hits_title = sum(1 for k in kw_clean.split() if k in title_company)
    keyword_hits_other = sum(
        1 for k in kw_clean.split() if k in f"{desc_lower} {job.location.lower()}"
    )
    score += keyword_hits_title * 20 + keyword_hits_other * 5

    # Level bonus: ONLY check title + company to avoid description false-positives
    level_map = {
        "entry": ["entry", "junior", "new grad", "graduate", "0-2", "0 - 2", "fresher"],
        "mid": ["mid", "intermediate", "2-5", "3-5", "2+ years"],
        "senior": ["senior", "sr.", "lead", "staff", "principal", "5-8", "5+ years", "8+ years"],
        "staff": ["staff", "principal", "architect", "director", "8+ years", "10+ years"],
    }
    for level_hint in level_map.get(config.experience_level, []):
        if level_hint in title_company:
            score += 15
            reasons.append(f"Matches {config.experience_level} level")
            break

    if config.remote_only and any(
        r in combined for r in ["remote", "work from home", "wfh", "anywhere"]
    ):
        score += 10
        reasons.append("Remote friendly")

    excluded_found = [ex for ex in config.exclude_keywords if ex.lower() in combined]
    if excluded_found:
        score -= 30 * len(excluded_found)
        reasons.append(f"Excluded keywords: {', '.join(excluded_found)}")

    salary_val = parse_salary(job.salary or "")

    if config.min_salary_lakhs and salary_val and salary_val > 10000:
        lakhs = salary_val / 100000
        if lakhs < config.min_salary_lakhs:
            score -= 30
            reasons.append(f"Salary {lakhs:.1f}L < {config.min_salary_lakhs}L")

    if config.min_salary and salary_val and salary_val >= 10000:
        if salary_val < config.min_salary:
            score -= 25
            reasons.append(f"Salary below ${config.min_salary}")

    # Run LLM on shorter descriptions too (many API feeds are concise)
    if len(job.description) > 50:
        prompt = f"""Rate this job relevance 0-100 for this candidate. Be concise.

Candidate: {profile[:600]}
Job: {job.title} at {job.company}
Description: {job.description[:1200]}
Keywords wanted: {config.keywords}
Exclude: {', '.join(config.exclude_keywords)}
Min salary: {config.min_salary or 'Any'}
Experience: {config.experience_level}

Respond ONLY as JSON: {{"score": 75, "salary": "$120k-$150k", "reason": "..."}}
If no salary, use null."""

        response = await ask_llm(prompt, model=config.llm_model, timeout=config.llm_timeout)
        try:
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                llm_score = float(result.get("score", score))
                llm_salary = result.get("salary")
                llm_reason = result.get("reason", "LLM evaluated")

                final_score = (llm_score * 0.6) + (min(score, 100) * 0.4)
                return final_score, llm_reason, llm_salary or job.salary
        except Exception as e:
            print(f"    LLM parse failed: {e}")

    final_score = min(max(score, 0), 100)
    reason = "; ".join(reasons) if reasons else "Keyword-based match"
    return final_score, reason, job.salary
