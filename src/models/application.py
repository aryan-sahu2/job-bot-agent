from datetime import datetime

from pydantic import BaseModel, Field


class Application(BaseModel):
    id: str
    job_id: str
    status: str = "draft"
    answers: dict[str, str] | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: datetime | None = None
