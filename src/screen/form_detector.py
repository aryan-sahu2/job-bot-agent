"""DOM-based form field detector."""

from __future__ import annotations

import logging
from typing import Any

from src.screen.models import DetectedField, FieldType
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

# Standard field mappings
STANDARD_FIELDS = {
    "first_name": ["first name", "given name", "fname", "first"],
    "last_name": ["last name", "surname", "family name", "lname", "last"],
    "email": ["email", "e-mail", "email address", "your email"],
    "phone": ["phone", "telephone", "mobile", "cell", "phone number", "contact number"],
    "resume": ["resume", "cv", "upload resume", "upload cv", "attach resume"],
    "cover_letter": ["cover letter", "coverletter", "additional info", "message", "why you"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "github": ["github", "github url", "github profile"],
    "website": ["website", "portfolio", "personal website", "url"],
    "company": ["company", "current company", "employer", "organization"],
    "position": ["position", "title", "job title", "role", "current position"],
}


class FormDetector:
    def __init__(self, reader: ScreenReader) -> None:
        self._reader = reader

    async def detect_fields(self) -> list[DetectedField]:
        """Detect all form fields in the current page DOM."""
        page = await self._reader.get_page()

        # Query all input-like elements
        elements = await page.query_selector_all(
            "input:not([type='hidden']), textarea, select, "
            "[contenteditable='true'], [role='textbox'], [role='combobox']"
        )

        fields: list[DetectedField] = []
        for el in elements:
            field = await self._analyze_element(el)
            if field:
                fields.append(field)

        logger.info("Detected %d form field(s)", len(fields))
        return fields

    async def _analyze_element(self, element: Any) -> DetectedField | None:
        try:
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.evaluate("el => el.type?.toLowerCase() || ''")
            name = await element.evaluate("el => el.name || ''")
            id_val = await element.evaluate("el => el.id || ''")
            placeholder = await element.evaluate("el => el.placeholder || ''")
            required = await element.evaluate("el => el.required || false")
            aria_label = await element.evaluate("el => el.getAttribute('aria-label') || ''")

            # Build label text
            label_text = await self._find_label(element, id_val)
            combined_text = f"{label_text} {placeholder} {aria_label} {name} {id_val}".lower()

            # Determine field type
            field_type = self._determine_type(tag, input_type, combined_text)

            # Get selector for filling
            selector = await self._build_selector(element, id_val, name)

            return DetectedField(
                role=tag,
                title=label_text or placeholder or aria_label or name or id_val,
                description=placeholder or aria_label,
                value="",
                identifier=selector,
                field_type=field_type,
                element_ref=element,
                required=required,
            )
        except Exception as e:
            logger.debug("Failed to analyze element: %s", e)
            return None

    async def _find_label(self, element: Any, element_id: str) -> str:
        """Find label text for an element."""
        # Try aria-labelledby
        labelled_by = await element.evaluate("el => el.getAttribute('aria-labelledby') || ''")
        if labelled_by:
            page = await self._reader.get_page()
            label_el = await page.query_selector(f"#{labelled_by}")
            if label_el:
                text = await label_el.inner_text()
                return text.strip() if text else ""

        # Try label[for=id]
        if element_id:
            page = await self._reader.get_page()
            label_el = await page.query_selector(f"label[for='{element_id}']")
            if label_el:
                text = await label_el.inner_text()
                return text.strip() if text else ""

        # Try parent label
        label_text = await element.evaluate(
            "el => el.closest('label')?.textContent?.trim() || ''"
        )
        if label_text:
            return label_text

        # Try preceding sibling text
        prev_text = await element.evaluate("""
            el => {
                let prev = el.previousElementSibling;
                while (prev) {
                    if (prev.textContent?.trim()) return prev.textContent.trim();
                    prev = prev.previousElementSibling;
                }
                return '';
            }
        """)
        return prev_text

    def _determine_type(self, tag: str, input_type: str, label_text: str) -> FieldType:
        # Check label keywords first
        for field_name, keywords in STANDARD_FIELDS.items():
            if any(kw in label_text for kw in keywords):
                if field_name == "email":
                    return FieldType.EMAIL
                elif field_name == "phone":
                    return FieldType.PHONE
                elif field_name == "resume":
                    return FieldType.FILE
                elif field_name == "cover_letter":
                    return FieldType.TEXTAREA
                elif field_name == "linkedin" or field_name == "github" or field_name == "website":
                    return FieldType.URL

        # Check input type
        if tag == "select":
            return FieldType.SELECT
        elif tag == "textarea":
            return FieldType.TEXTAREA
        elif input_type == "checkbox":
            return FieldType.CHECKBOX
        elif input_type == "radio":
            return FieldType.RADIO
        elif input_type == "file":
            return FieldType.FILE
        elif input_type == "email":
            return FieldType.EMAIL
        elif input_type == "tel":
            return FieldType.PHONE
        elif input_type == "url":
            return FieldType.URL
        elif input_type in ("date", "datetime-local"):
            return FieldType.DATE
        elif input_type in ("number", "text", "search", "password"):
            # Check label for clues
            if any(k in label_text for k in ["name", "first", "last", "full"]):
                return FieldType.NAME
            return FieldType.TEXT

        return FieldType.TEXT

    async def _build_selector(self, element: Any, id_val: str, name: str) -> str:
        """Build a robust CSS selector for the element."""
        if id_val:
            return f"#{id_val}"
        if name:
            return f"[name='{name}']"
        # Fallback: generate xpath or nth-child (less robust)
        return await element.evaluate("""
            el => {
                const path = [];
                let curr = el;
                while (curr && curr.tagName !== 'BODY') {
                    let selector = curr.tagName.toLowerCase();
                    if (curr.id) {
                        selector += '#' + curr.id;
                        path.unshift(selector);
                        break;
                    }
                    if (curr.className) {
                        selector += '.' + curr.className.split(' ').join('.');
                    }
                    const siblings = Array.from(curr.parentNode?.children || []);
                    const sameTag = siblings.filter(s => s.tagName === curr.tagName);
                    if (sameTag.length > 1) {
                        const index = sameTag.indexOf(curr) + 1;
                        selector += `:nth-of-type(${index})`;
                    }
                    path.unshift(selector);
                    curr = curr.parentNode;
                }
                return path.join(' > ');
            }
        """)

    def map_to_standard_field(self, field: DetectedField) -> str | None:
        label_text = f"{field.title} {field.description} {field.identifier}".lower()
        for standard_name, patterns in STANDARD_FIELDS.items():
            if any(pat in label_text for pat in patterns):
                return standard_name
        return None

    def is_upload_field(self, field: DetectedField) -> bool:
        return field.field_type == FieldType.FILE

    def is_dropdown_field(self, field: DetectedField) -> bool:
        return field.field_type == FieldType.SELECT

    def get_required_fields(self, fields: list[DetectedField]) -> list[DetectedField]:
        return [f for f in fields if f.required]

    def get_optional_fields(self, fields: list[DetectedField]) -> list[DetectedField]:
        return [f for f in fields if not f.required]