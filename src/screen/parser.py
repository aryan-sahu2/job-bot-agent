"""Job description parser using DOM content."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.screen.models import ScreenJob
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

# Site-specific CSS selectors
SELECTORS = {
    "linkedin": {
        "title": "h1, .top-card-layout__title, .job-details-jobs-unified-top-card__job-title",
        "company": "[class*='company-name'], a[href*='/company/']",
        "location": "[class*='location'], [class*='bullet']",
        "description": "[class*='description'], [class*='jobs-description']",
    },
    "indeed": {
        "title": "h1[data-testid='jobTitle'], .jobsearch-JobInfoHeader-title",
        "company": "[data-testid='company-name'], [class*='company']",
        "location": "[data-testid='job-location']",
        "description": "#jobDescriptionText, [data-testid='jobDescriptionText']",
    },
    "greenhouse": {
        "title": ".app-title, h1",
        "company": ".company-name, h2",
        "location": ".location",
        "description": ".content, #content",
    },
    "lever": {
        "title": ".posting-headline h2, .job-title",
        "company": ".main-header-logo, .company-name",
        "location": ".sort-by-time, .location",
        "description": ".content, .posting-page, .posting-description",
    },
    "wellfound": {
        "title": "[data-test='role-title'], h1",
        "company": "[data-test='company-name']",
        "location": "[data-test='location']",
        "description": "[data-test='description']",
    },
    "workday": {
        "title": "[data-automation-id='jobPostingHeader'], h1",
        "company": "[data-automation-id='jobPostingHeader']",
        "location": "[data-automation-id='jobLocation']",
        "description": "[data-automation-id='jobDescription']",
    },
}

GENERIC = {
    "title": "h1, [class*='job-title'], [class*='jobTitle']",
    "company": "[class*='company'], [class*='employer']",
    "location": "[class*='location']",
    "description": "[class*='description'], [class*='job-description'], article, main",
}


class JobDescriptionParser:
    def __init__(self, reader: ScreenReader) -> None:
        self._reader = reader

    async def parse(self) -> ScreenJob:
        logger.info("Parsing job from current page")

        url = await self._reader.url()
        html = await self._reader.content()
        text = await self._reader.visible_text()

        site = self._detect_site(url)

        title = await self._extract(site, "title") or self._extract_title_heuristic(text, html)
        company = await self._extract(site, "company") or self._extract_company_heuristic(text, html)
        location = await self._extract(site, "location") or self._extract_location_heuristic(text)
        description = await self._extract(site, "description") or self._extract_description_heuristic(text, html)

        return ScreenJob(
            title=title or "",
            company=company or "",
            location=location or "",
            description=description or text[:5000],
            requirements=self._extract_requirements(description or text),
            url=url,
        )

    def _detect_site(self, url: str) -> str:
        url_l = url.lower()
        if "linkedin.com" in url_l:
            return "linkedin"
        elif "indeed." in url_l:
            return "indeed"
        elif "greenhouse.io" in url_l:
            return "greenhouse"
        elif "lever.co" in url_l:
            return "lever"
        elif "wellfound.com" in url_l or "angel.co" in url_l:
            return "wellfound"
        elif "myworkdayjobs.com" in url_l or "workday" in url_l:
            return "workday"
        return "generic"

    async def _extract(self, site: str, field: str) -> str | None:
        sel_map = SELECTORS.get(site, GENERIC)
        selector = sel_map.get(field, "")
        if not selector:
            return None
        try:
            el = await self._reader.query(selector)
            if el:
                text = await el.inner_text()
                return text.strip() if text else None
        except Exception as e:
            logger.debug("Selector %s failed: %s", selector, e)
        return None

    def _extract_title_heuristic(self, text: str, html: str) -> str | None:
        # h1 tag
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if len(title) < 100 and any(k in title.lower() for k in ["engineer", "developer", "manager", "designer", "analyst", "scientist", "lead", "director"]):
                return title
        # First substantial line
        for line in text.split("\n")[:10]:
            line = line.strip()
            if 10 < len(line) < 100 and any(k in line.lower() for k in ["engineer", "developer", "manager", "designer", "lead", "director", "specialist"]):
                return line
        return None

    def _extract_company_heuristic(self, text: str, html: str) -> str | None:
        # Meta tag
        m = re.search(r'<meta[^>]*property="og:site_name"[^>]*content="([^"]+)"', html)
        if m:
            return m.group(1)
        # "at Company" pattern
        m = re.search(r"\bat\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*[|\-—]|\s*$)", text[:2000])
        if m:
            return m.group(1).strip()
        # URL domain
        m = re.search(r"https?://(?:www\.)?([^/]+)", text)
        if m:
            domain = m.group(1)
            if domain not in ("linkedin.com", "indeed.com", "greenhouse.io"):
                return domain.replace("-", " ").title()
        return None

    def _extract_location_heuristic(self, text: str) -> str | None:
        for line in text.split("\n")[:30]:
            line = line.strip()
            if any(k in line.lower() for k in ["remote", "hybrid", "onsite", "on-site", "full-time", "part-time", "contract"]):
                return line
            if "," in line and len(line) < 60 and not line.startswith("http"):
                # City, State/Country pattern
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 2 and all(p.isascii() for p in parts):
                    return line
        return None

    def _extract_description_heuristic(self, text: str, html: str) -> str | None:
        # Largest text block heuristic
        lines = text.split("\n")
        chunks = []
        current = []
        for line in lines:
            if line.strip():
                current.append(line.strip())
            else:
                if len(current) > 3:
                    chunks.append("\n".join(current))
                current = []
        if len(current) > 3:
            chunks.append("\n".join(current))

        if chunks:
            return max(chunks, key=len)

        # Fallback: body text minus first/last few lines
        lines = [l.strip() for l in lines if l.strip()]
        if len(lines) > 10:
            return "\n".join(lines[3:-3])
        return "\n".join(lines)

    def _extract_requirements(self, text: str) -> list[str]:
        reqs = []
        lines = text.split("\n")
        in_req = False
        req_headers = ["requirements", "qualifications", "what we're looking for", "what you need", "must have"]
        for line in lines:
            low = line.lower().strip()
            if any(h in low for h in req_headers):
                in_req = True
                continue
            if in_req:
                if any(skip in low for skip in ["about us", "benefits", "perks", "salary", "compensation", "how to apply"]):
                    if not low.startswith(("•", "-", "*")):
                        in_req = False
                        continue
                if low.startswith(("•", "-", "*", "✓")):
                    req = low.lstrip("•-*✓").strip()
                    if len(req) > 10:
                        reqs.append(req)
                elif len(line.strip()) > 20 and not line.strip().startswith("http"):
                    reqs.append(line.strip())
        return reqs