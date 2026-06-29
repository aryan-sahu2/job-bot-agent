from dataclasses import dataclass, field


@dataclass
class SearchConfig:
    keywords: str = "Full Stack Developer"
    location: str = "Remote"
    min_salary: int | None = 120000
    remote_only: bool = True
    experience_level: str = "mid"
    exclude_keywords: list[str] = field(default_factory=lambda: ["php", "wordpress", "salesforce", "drupal"])

    linkedin_time_filter: str = "r6400"
    linkedin_remote_filter: str = "2"
    linkedin_distance: str = "25"

    naukri_experience: str = ""
    naukri_salary_lakhs: str = ""

    def __post_init__(self):
        if isinstance(self.exclude_keywords, str):
            self.exclude_keywords = [k.strip() for k in self.exclude_keywords.split(",")]
