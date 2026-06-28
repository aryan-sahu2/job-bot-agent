"""Job description parser from accessibility tree."""

from __future__ import annotations

import logging
from typing import Any

from src.screen.models import ScreenJob
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

# Common job-related section headers
JOB_SECTIONS = [
    "about the role",
    "about us",
    "about you",
    "requirements",
    "qualifications",
    "what you'll do",
    "responsibilities",
    "what we're looking for",
    "nice to have",
    "benefits",
    "perks",
    "salary",
    "compensation",
    "location",
    "remote",
    "about the company",
    "our stack",
    "tech stack",
    "how to apply",
]

# Patterns to identify job-related content
JOB_PATTERNS = [
    r"(?:job|position|role)\s+(?:title|description|summary)",
    r"(?:we|they)\s+(?:are|is)\s+looking\s+for",
    r"(?:ideal|perfect)\s+candidate",
    r"(?:experience|skills|required|preferred)",
    r"(?:benefits|perks|compensation|salary)",
]


class JobDescriptionParser:
    """Parses job descriptions from the current browser window's accessibility tree.

    Identifies job-related content by analyzing the UI structure and text content.
    Handles scrolling to capture full job descriptions.
    """

    def __init__(
        self,
        reader: ScreenReader,
        max_scroll_attempts: int = 5,
        scroll_pause: float = 0.5,
    ) -> None:
        """Initialize the parser.

        Args:
            reader: The ScreenReader instance for accessing the UI.
            max_scroll_attempts: Maximum number of scroll attempts to read full content.
            scroll_pause: Seconds to wait between scroll attempts.
        """
        self._reader = reader
        self._max_scroll_attempts = max_scroll_attempts
        self._scroll_pause = scroll_pause

    def parse(self, window_element: Any | None = None) -> ScreenJob:
        """Parse the current window content to extract job information.

        Args:
            window_element: The window to parse. If None, uses the focused window.

        Returns:
            ScreenJob with extracted information.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()

        if window_element is None:
            logger.warning("No focused window found")
            return ScreenJob()

        logger.info("Parsing job description from current window")

        url = self._reader.get_window_url(window_element)
        title = self._extract_job_title(window_element)
        company = self._extract_company(window_element)
        location = self._extract_location(window_element)

        description = self._extract_full_description(window_element)
        requirements = self._extract_requirements(description)

        job = ScreenJob(
            title=title,
            company=company,
            location=location,
            description=description,
            requirements=requirements,
            url=url,
        )

        logger.info(
            "Parsed job: title='%s', company='%s', location='%s', desc_len=%d",
            job.title,
            job.company,
            job.location,
            len(job.description),
        )
        return job

    def _extract_job_title(self, window_element: Any) -> str:
        """Extract the job title from the window."""
        title = self._reader.get_attribute(window_element, "AXTitle")
        if title:
            return str(title).strip()

        children = self._reader.get_children(window_element)
        for child in children[:10]:
            role = self._reader.get_attribute(child, "AXRole")
            title_val = self._reader.get_attribute(child, "AXTitle")
            if role == "AXStaticText" and title_val:
                text = str(title_val).strip()
                if self._looks_like_job_title(text):
                    return text
        return ""

    def _extract_company(self, window_element: Any) -> str:
        """Extract the company name from the window."""
        children = self._reader.get_children(window_element)
        for child in children[:20]:
            role = self._reader.get_attribute(child, "AXRole")
            value = self._reader.get_attribute(child, "AXValue")
            if role == "AXStaticText" and value:
                text = str(value).strip()
                if self._looks_like_company_name(text):
                    return text
        return ""

    def _extract_location(self, window_element: Any) -> str:
        """Extract the job location from the window."""
        children = self._reader.get_children(window_element)
        for child in children[:20]:
            role = self._reader.get_attribute(child, "AXRole")
            value = self._reader.get_attribute(child, "AXValue")
            if role == "AXStaticText" and value:
                text = str(value).strip()
                if self._looks_like_location(text):
                    return text
        return ""

    def _extract_full_description(self, window_element: Any) -> str:
        """Extract the full job description text, scrolling if needed."""
        all_texts: list[str] = []

        for _ in range(self._max_scroll_attempts):
            current_text = self._reader.get_all_text(window_element, max_depth=20)
            if current_text not in all_texts:
                all_texts.append(current_text)

            if not self._scroll_down(window_element):
                break

        combined = "\n\n".join(all_texts)
        cleaned = self._clean_description(combined)
        return cleaned

    def _scroll_down(self, window_element: Any) -> bool:
        """Scroll down and return True if new content might be available."""
        import time

        # Try scrolling the window element directly
        if self._reader.scroll_down(window_element):
            time.sleep(self._scroll_pause)
            return True

        # Fallback: try scrolling the largest child (likely the content area)
        children = self._reader.get_children(window_element)
        for child in children:
            if self._reader.scroll_down(child):
                time.sleep(self._scroll_pause)
                return True

        return False

    def _clean_description(self, text: str) -> str:
        """Clean and normalize the extracted description text."""
        lines = text.split("\n")
        cleaned: list[str] = []
        seen: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                cleaned.append(stripped)

        return "\n".join(cleaned)

    def _extract_requirements(self, description: str) -> list[str]:
        """Extract requirements from the job description."""
        requirements: list[str] = []
        lines = description.split("\n")

        in_requirements = False
        for line in lines:
            lower = line.lower().strip()

            req_headers = ["requirements", "qualifications", "what we're looking for"]
            if any(header in lower for header in req_headers):
                in_requirements = True
                continue

            if in_requirements:
                skip_headers = JOB_SECTIONS
                is_skip_header = any(header in lower for header in skip_headers)
                is_bullet = lower.startswith(("•", "-", "*", "✓"))
                if is_skip_header and not is_bullet:
                    in_requirements = False
                    continue

                if line.strip().startswith(("•", "-", "*", "✓")):
                    req = line.strip().lstrip("•-*✓").strip()
                    if req:
                        requirements.append(req)
                elif len(line.strip()) > 10 and not line.strip().startswith(("http", "www")):
                    requirements.append(line.strip())

        return requirements

    def _looks_like_job_title(self, text: str) -> bool:
        """Heuristic to check if text looks like a job title."""
        if len(text) > 100:
            return False
        title_keywords = [
            "engineer", "developer", "manager", "designer", "analyst",
            "scientist", "architect", "lead", "director", "intern",
            "specialist", "coordinator", "consultant", "associate",
        ]
        return any(kw in text.lower() for kw in title_keywords)

    def _looks_like_company_name(self, text: str) -> bool:
        """Heuristic to check if text looks like a company name."""
        if len(text) > 50 or len(text) < 2:
            return False
        if text[0].isdigit():
            return False
        skip_words = ["apply", "save", "share", "sign", "log", "back", "home"]
        if text.lower() in skip_words:
            return False
        return True

    def _looks_like_location(self, text: str) -> bool:
        """Heuristic to check if text looks like a location."""
        location_keywords = [
            "remote", "hybrid", "onsite", "on-site",
            "full-time", "part-time", "contract",
        ]
        if any(kw in text.lower() for kw in location_keywords):
            return True
        if "," in text and len(text) < 50:
            return True
        return False
