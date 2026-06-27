from datetime import datetime

from pydantic import BaseModel, Field


class Evaluation(BaseModel):
    job_id: str
    match_score: int
    strengths: list[str]
    missing_skills: list[str]
    summary: str
    evaluated_at: datetime = Field(default_factory=datetime.now)
