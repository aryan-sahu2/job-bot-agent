"""Form field detection via accessibility APIs."""

from __future__ import annotations

import logging
from typing import Any

from src.screen.models import DetectedField, FieldType
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

# Mapping of field roles to our FieldType enum
ROLE_FIELD_MAP = {
    "AXTextField": FieldType.TEXT,
    "AXTextArea": FieldType.TEXTAREA,
    "AXComboBox": FieldType.SELECT,
    "AXPopUpButton": FieldType.SELECT,
    "AXCheckBox": FieldType.CHECKBOX,
    "AXRadioButton": FieldType.RADIO,
    "AXSlider": FieldType.TEXT,
}

# Keywords for detecting field types from labels/titles
FIELD_TYPE_KEYWORDS = {
    FieldType.EMAIL: ["email", "e-mail", "mail"],
    FieldType.PHONE: ["phone", "mobile", "telephone", "cell", "fax"],
    FieldType.NAME: ["name", "first name", "last name", "full name", "your name"],
    FieldType.URL: ["url", "link", "website", "portfolio", "github", "linkedin"],
    FieldType.DATE: ["date", "birth", "birthday", "start date", "available"],
    FieldType.FILE: ["upload", "resume", "cv", "cover letter", "attachment", "file"],
}

# Keywords for identifying which standard field a custom field maps to
STANDARD_FIELD_PATTERNS = {
    "first_name": ["first name", "given name", "fname"],
    "last_name": ["last name", "surname", "family name", "lname"],
    "email": ["email", "e-mail", "email address"],
    "phone": ["phone", "telephone", "mobile", "phone number", "contact number"],
    "resume": ["resume", "cv", "upload resume", "upload cv"],
    "cover_letter": ["cover letter", "cover letter (optional)", "additional info"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "github": ["github", "github url", "github profile"],
    "website": ["website", "portfolio", "personal website", "url"],
}


class FormDetector:
    """Detects form fields in the current window using accessibility APIs.

    Scans the accessibility tree for input fields, text areas, dropdowns,
    and other form elements. Maps them to standard field types.
    """

    def __init__(self, reader: ScreenReader) -> None:
        """Initialize the form detector.

        Args:
            reader: The ScreenReader instance for accessing the UI.
        """
        self._reader = reader

    def detect_fields(
        self,
        window_element: Any | None = None,
    ) -> list[DetectedField]:
        """Detect all form fields in the current window.

        Args:
            window_element: The window to scan. If None, uses focused window.

        Returns:
            List of DetectedField instances.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()

        if window_element is None:
            logger.warning("No focused window found")
            return []

        fields: list[DetectedField] = []
        self._search_for_fields(window_element, fields, depth=0, max_depth=15)
        logger.info("Detected %d form field(s)", len(fields))
        return fields

    def _search_for_fields(
        self,
        element: Any,
        results: list[DetectedField],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively search for form fields in the accessibility tree."""
        if depth > max_depth:
            return

        try:
            role = self._reader.get_attribute(element, "AXRole")

            if role in ROLE_FIELD_MAP:
                field = self._create_detected_field(element, role)
                if field:
                    results.append(field)
                    logger.debug(
                        "Detected field: type='%s', title='%s'",
                        field.field_type,
                        field.title,
                    )

            children = self._reader.get_children(element)
            for child in children:
                self._search_for_fields(child, results, depth + 1, max_depth)
        except Exception:
            logger.debug("Error searching element at depth %d", depth)

    def _create_detected_field(self, element: Any, role: str) -> DetectedField | None:
        """Create a DetectedField from an accessibility element."""
        try:
            title = str(self._reader.get_attribute(element, "AXTitle") or "")
            description = str(self._reader.get_attribute(element, "AXDescription") or "")
            value = str(self._reader.get_attribute(element, "AXValue") or "")
            identifier = str(self._reader.get_attribute(element, "AXIdentifier") or "")
            required = bool(self._reader.get_attribute(element, "AXRequired"))

            label_text = f"{title} {description} {identifier}".lower()

            field_type = ROLE_FIELD_MAP.get(role, FieldType.UNKNOWN)

            if field_type == FieldType.TEXT:
                detected_type = self._detect_text_field_type(label_text, value)
                if detected_type:
                    field_type = detected_type

            return DetectedField(
                role=role,
                title=title,
                description=description,
                value=value,
                identifier=identifier,
                field_type=field_type,
                element_ref=element,
                required=required,
            )
        except Exception:
            logger.exception("Error creating DetectedField")
            return None

    def _detect_text_field_type(self, label_text: str, current_value: str) -> FieldType | None:
        """Detect the specific type of a text field from its label."""
        for field_type, keywords in FIELD_TYPE_KEYWORDS.items():
            if any(kw in label_text for kw in keywords):
                return field_type
        return None

    def map_to_standard_field(self, field: DetectedField) -> str | None:
        """Map a detected field to a standard field name.

        Returns:
            Standard field name (e.g., "first_name", "email") or None if custom.
        """
        label_text = f"{field.title} {field.description} {field.identifier}".lower()

        for standard_name, patterns in STANDARD_FIELD_PATTERNS.items():
            if any(pat in label_text for pat in patterns):
                return standard_name

        return None

    def is_upload_field(self, field: DetectedField) -> bool:
        """Check if a field is a file upload field."""
        return field.field_type == FieldType.FILE

    def is_dropdown_field(self, field: DetectedField) -> bool:
        """Check if a field is a dropdown/select field."""
        return field.field_type == FieldType.SELECT

    def get_required_fields(self, fields: list[DetectedField]) -> list[DetectedField]:
        """Filter fields to only required ones."""
        return [f for f in fields if f.required]

    def get_optional_fields(self, fields: list[DetectedField]) -> list[DetectedField]:
        """Filter fields to only optional ones."""
        return [f for f in fields if not f.required]
