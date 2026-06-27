import re

from src.profile.models import Education, Experience, Profile

SECTION_HEADERS: dict[str, str] = {
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "work history": "experience",
    "education": "education",
    "academic background": "education",
    "skills": "skills",
    "technical skills": "skills",
    "core competencies": "skills",
    "summary": "summary",
    "professional summary": "summary",
    "profile": "summary",
    "links": "links",
    "profiles": "links",
    "connect": "links",
    "projects": "projects",
    "certifications": "certifications",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
URL_RE = re.compile(r"https?://(?:www\.)?[a-zA-Z0-9./_-]+")


class ResumeParser:
    def parse(self, text: str) -> Profile:
        lines = text.strip().split("\n")
        header_lines = self._extract_header_lines(lines)
        email = self._find_email(header_lines)
        phone = self._find_phone(header_lines)
        urls = self._find_urls(text)
        sections = self._split_sections(lines)
        name = self._extract_name(header_lines, sections)
        title = self._extract_title(header_lines)
        location = self._extract_location(header_lines)
        summary = self._extract_summary(sections)
        skills = self._extract_skills(sections)
        experience = self._extract_experience(sections)
        education = self._extract_education(sections)

        if not name:
            name = header_lines[0].strip() if header_lines else "Unknown"

        return Profile(
            name=name,
            email=email,
            phone=phone,
            location=location,
            title=title,
            skills=skills,
            experience=experience,
            education=education,
            urls=urls,
            summary=summary,
        )

    def _extract_header_lines(self, lines: list[str]) -> list[str]:
        header: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_section_header(stripped):
                break
            header.append(stripped)
        return header

    @staticmethod
    def _is_section_header(line: str) -> bool:
        cleaned = line.strip().lower().rstrip(":")
        return cleaned in SECTION_HEADERS or (
            line.isupper() and len(line.split()) <= 4 and len(line) > 3
        )

    @staticmethod
    def _find_email(lines: list[str]) -> str | None:
        for line in lines:
            match = EMAIL_RE.search(line)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _find_phone(lines: list[str]) -> str | None:
        for line in lines:
            match = PHONE_RE.search(line)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def _find_urls(text: str) -> list[str]:
        return URL_RE.findall(text)

    @staticmethod
    def _extract_name(headers: list[str], sections: dict[str, list[str]]) -> str:
        for line in headers:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("http"):
                email_match = EMAIL_RE.search(cleaned)
                phone_match = PHONE_RE.search(cleaned)
                url_match = URL_RE.search(cleaned)
                if not email_match and not phone_match and not url_match:
                    return cleaned
        return ""

    @staticmethod
    def _extract_title(headers: list[str]) -> str | None:
        if len(headers) >= 2:
            candidate = headers[1].strip()
            email_match = EMAIL_RE.search(candidate)
            phone_match = PHONE_RE.search(candidate)
            url_match = URL_RE.search(candidate)
            if not email_match and not phone_match and not url_match:
                return candidate
        return None

    @staticmethod
    def _extract_location(headers: list[str]) -> str | None:
        for line in headers:
            cleaned = line.strip()
            if "," in cleaned and not EMAIL_RE.search(cleaned):
                parts = [p.strip() for p in cleaned.split(",")]
                if len(parts) == 2 and all(p.isascii() for p in parts):
                    return cleaned
        return None

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            header_key = self._detect_section(stripped)
            if header_key:
                if current_section and current_lines:
                    sections[current_section] = current_lines
                current_section = header_key
                current_lines = []
            elif current_section:
                if stripped:
                    current_lines.append(stripped)

        if current_section and current_lines:
            sections[current_section] = current_lines

        return sections

    @staticmethod
    def _detect_section(line: str) -> str | None:
        cleaned = line.strip().lower().rstrip(":")
        if cleaned in SECTION_HEADERS:
            return SECTION_HEADERS[cleaned]
        if line.isupper() and len(line.split()) <= 4 and len(line) > 3:
            cleaned_upper = line.strip().lower().rstrip(":")
            if cleaned_upper in SECTION_HEADERS:
                return SECTION_HEADERS[cleaned_upper]
            return "other"
        return None

    @staticmethod
    def _extract_summary(sections: dict[str, list[str]]) -> str | None:
        lines = sections.get("summary", [])
        if lines:
            return " ".join(lines)
        return None

    @staticmethod
    def _extract_skills(sections: dict[str, list[str]]) -> list[str]:
        skills: list[str] = []
        for line in sections.get("skills", []):
            items = [s.strip() for s in re.split(r"[,|•·\-;]", line) if s.strip()]
            skills.extend(items)
        return skills

    def _extract_experience(self, sections: dict[str, list[str]]) -> list[Experience]:
        experiences: list[Experience] = []
        lines = sections.get("experience", [])
        i = 0
        while i < len(lines):
            line = lines[i]
            if "\t" in line or "  " in line:
                parts = re.split(r"\t{1,}|\s{2,}", line)
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) >= 2:
                    company = parts[0]
                    title = parts[1] if len(parts) >= 2 else parts[0]
                    dates = parts[2] if len(parts) >= 3 else None
                    description_lines: list[str] = []
                    i += 1
                    while i < len(lines) and not self._looks_like_new_entry(lines[i]):
                        description_lines.append(lines[i])
                        i += 1
                    experiences.append(
                        Experience(
                            title=title,
                            company=company,
                            description=self._parse_dates_and_desc(dates, description_lines)[
                                1
                            ]
                            if dates
                            else " ".join(description_lines),
                            start_date=self._parse_date_range(dates)[0] if dates else None,
                            end_date=self._parse_date_range(dates)[1] if dates else None,
                        )
                    )
                    continue
            i += 1
        return experiences

    @staticmethod
    def _looks_like_new_entry(line: str) -> bool:
        return ("\t" in line or "  " in line) and len(line.split()) >= 2

    @staticmethod
    def _parse_date_range(text: str) -> tuple[str | None, str | None]:
        date_match = re.search(
            r"(\w+\s+\d{4})\s*(?:[-–to]+|–)\s*(\w+\s+\d{4}|Present|Current|Now)",
            text,
            re.IGNORECASE,
        )
        if date_match:
            return date_match.group(1), date_match.group(2)
        return None, None

    @staticmethod
    def _parse_dates_and_desc(
        dates: str, desc_lines: list[str]
    ) -> tuple[str | None, str]:
        return None, " ".join(desc_lines)

    @staticmethod
    def _extract_education(sections: dict[str, list[str]]) -> list[Education]:
        education_list: list[Education] = []
        for line in sections.get("education", []):
            parts = [p.strip() for p in re.split(r"\s{2,}|,", line) if p.strip()]
            grad_year = None
            year_match = re.search(r"(\d{4})", line)
            if year_match:
                grad_year = year_match.group(1)
            degree = parts[0] if parts else line
            field = parts[1] if len(parts) > 1 else None
            institution = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
            education_list.append(
                Education(
                    degree=degree,
                    institution=institution,
                    field=field,
                    graduation_year=grad_year,
                )
            )
        return education_list
