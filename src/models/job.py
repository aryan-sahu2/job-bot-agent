from datetime import datetime

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str
    source: str
    company: str
    title: str
    location: str | None = None
    employment_type: str | None = None
    salary: str | None = None
    description: str
    skills: list[str] = Field(default_factory=list)
    apply_url: str | None = None
    posted_date: datetime | None = None
    metadata: dict = Field(default_factory=dict)
