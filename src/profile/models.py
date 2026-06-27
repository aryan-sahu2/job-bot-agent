from pydantic import BaseModel, Field


class Experience(BaseModel):
    title: str
    company: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Education(BaseModel):
    degree: str
    institution: str
    field: str | None = None
    graduation_year: str | None = None


class Profile(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    title: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    summary: str | None = None


class Resume(BaseModel):
    raw_text: str
    profile: Profile
    file_path: str | None = None
