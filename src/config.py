import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = {
    "keywords": "Full Stack Engineer",
    "location": "Remote",
    "min_salary": None,
    "min_salary_lakhs": 15.0,
    "remote_only": True,
    "experience_level": "mid",
    "exclude_keywords": ["php", "wordpress", "salesforce", "drupal"],
    "hours_since_posted": 4,
    "startup_only": False,
    "linkedin_time_filter": "r86400",
    "linkedin_remote_filter": "2",
    "linkedin_distance": "25",
    "naukri_experience": "",
    "naukri_salary_lakhs": "",
    "greenhouse_boards": [],
    "lever_slugs": [],
    "max_jobs_per_source": 15,
    "llm_api": "http://localhost:11434/api/generate",
    "llm_model": "gemma3",
    "llm_timeout": 90,
    "output_dir": "output",
    "resume_path": "resume.txt",
}


@dataclass
class SearchConfig:
    keywords: str = "Full Stack Engineer"
    location: str = "Remote"
    min_salary: int | None = None
    min_salary_lakhs: float | None = None
    remote_only: bool = True
    experience_level: str = "mid"
    exclude_keywords: list[str] = field(
        default_factory=lambda: ["php", "wordpress", "salesforce", "drupal"]
    )
    hours_since_posted: int = 4
    startup_only: bool = False
    linkedin_time_filter: str = "r86400"
    linkedin_remote_filter: str = "2"
    linkedin_distance: str = "25"
    naukri_experience: str = ""
    naukri_salary_lakhs: str = ""
    greenhouse_boards: list[str] = field(default_factory=list)
    lever_slugs: list[str] = field(default_factory=list)
    max_jobs_per_source: int = 15
    llm_api: str = "http://localhost:11434/api/generate"
    llm_model: str = "gemma3"
    llm_timeout: int = 90
    output_dir: str = "output"
    resume_path: str = "resume.txt"

    def __post_init__(self):
        if isinstance(self.exclude_keywords, str):
            self.exclude_keywords = [
                k.strip() for k in self.exclude_keywords.split(",") if k.strip()
            ]
        if isinstance(self.greenhouse_boards, str):
            self.greenhouse_boards = [
                k.strip() for k in self.greenhouse_boards.split(",") if k.strip()
            ]
        if isinstance(self.lever_slugs, str):
            self.lever_slugs = [
                k.strip() for k in self.lever_slugs.split(",") if k.strip()
            ]


def load_config(path: str | Path = "config.json") -> SearchConfig:
    path = Path(path)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        print(f"\n{'='*60}")
        print(f"Created default config at {path}")
        print("Edit it with your preferences, then run again.")
        print(f"{'='*60}\n")
        return SearchConfig()

    data = json.loads(path.read_text())
    merged = {**DEFAULT_CONFIG, **data}
    return SearchConfig(**merged)
