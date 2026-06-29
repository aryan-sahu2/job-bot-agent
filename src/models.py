import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    salary: Optional[str] = None
    description: str = ""
    source: str = ""
    posted_date: Optional[str] = None
    relevance_score: float = 0.0
    reason: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "salary": self.salary,
            "description": self.description[:500],
            "source": self.source,
            "score": self.relevance_score,
            "reason": self.reason,
        }


def parse_salary(salary_str: str) -> int | None:
    if not salary_str:
        return None
    nums = re.findall(r"[\d,]+", salary_str.replace(",", ""))
    if not nums:
        return None
    vals = [int(n) for n in nums if n.isdigit()]
    if not vals:
        return None
    min_val = min(vals)
    if min_val < 100:
        min_val *= 1000
    return min_val
