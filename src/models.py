import re
from dataclasses import dataclass
from datetime import datetime, timedelta
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
            "posted_date": self.posted_date,
            "score": self.relevance_score,
            "reason": self.reason,
        }


def parse_salary(salary_str: str) -> int | None:
    if not salary_str:
        return None

    lpa_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:[-–]\s*\d+(?:\.\d+)?)?\s*LPA",
        salary_str,
        re.IGNORECASE,
    )
    if lpa_match:
        return int(float(lpa_match.group(1)) * 100000)

    inr_match = re.search(r"₹?\s*([\d,]+)(?:\s*[-–]\s*₹?\s*[\d,]+)?", salary_str)
    if inr_match:
        val = int(inr_match.group(1).replace(",", ""))
        if val > 10000:
            return val

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


def parse_relative_time(time_str: str) -> Optional[datetime]:
    if not time_str:
        return None

    s = time_str.lower().strip()
    now = datetime.now()

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        pass

    patterns = [
        (r"(\d+)\s*hour", "hours"),
        (r"(\d+)\s*hr", "hours"),
        (r"(\d+)\s*minute", "minutes"),
        (r"(\d+)\s*min", "minutes"),
        (r"(\d+)\s*day", "days"),
        (r"(\d+)\s*week", "weeks"),
        (r"(\d+)\s*month", "months"),
    ]
    for pat, unit in patterns:
        m = re.search(pat, s)
        if m:
            val = int(m.group(1))
            delta = {
                "hours": timedelta(hours=val),
                "minutes": timedelta(minutes=val),
                "days": timedelta(days=val),
                "weeks": timedelta(weeks=val),
                "months": timedelta(days=val * 30),
            }[unit]
            return now - delta

    if any(x in s for x in ["just now", "today", "few hours"]):
        return now - timedelta(hours=1)

    return None
