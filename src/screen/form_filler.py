"""Accessibility-based form filler."""

from __future__ import annotations

import logging

from src.screen.form_detector import FormDetector
from src.screen.models import DetectedField, FieldType
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)


class FormFiller:
    """Fills form fields using macOS Accessibility APIs.

    Handles text inputs, text areas, dropdowns, checkboxes, and file uploads
    by setting values through the accessibility API.
    """

    def __init__(
        self,
        reader: ScreenReader,
        detector: FormDetector,
    ) -> None:
        """Initialize the form filler.

        Args:
            reader: The ScreenReader instance for interacting with the UI.
            detector: The FormDetector instance for identifying fields.
        """
        self._reader = reader
        self._detector = detector

    def fill_field(self, field: DetectedField, value: str) -> bool:
        """Fill a single detected field with a value.

        Args:
            field: The DetectedField to fill.
            value: The value to set.

        Returns:
            True if the fill succeeded, False otherwise.
        """
        if field.element_ref is None:
            logger.error("Field '%s' has no element reference", field.title)
            return False

        logger.info("Filling field '%s' (type=%s)", field.title, field.field_type)

        success = False

        match field.field_type:
            case FieldType.TEXT | FieldType.EMAIL | FieldType.PHONE:
                success = self._fill_text_field(field, value)
            case FieldType.URL | FieldType.DATE:
                success = self._fill_text_field(field, value)
            case FieldType.TEXTAREA:
                success = self._fill_textarea(field, value)
            case FieldType.SELECT:
                success = self._fill_dropdown(field, value)
            case FieldType.CHECKBOX:
                success = self._fill_checkbox(field, value)
            case FieldType.RADIO:
                success = self._fill_radio(field, value)
            case FieldType.FILE:
                logger.info("File upload field '%s' - requires manual upload", field.title)
                success = True
            case _:
                success = self._fill_text_field(field, value)

        if success:
            logger.info("Successfully filled field '%s'", field.title)
        else:
            logger.warning("Failed to fill field '%s'", field.title)

        return success

    def _fill_text_field(self, field: DetectedField, value: str) -> bool:
        """Fill a text input field.

        Strategy (tried in order):
        1. Mouse click + keyboard typing — triggers real DOM events in browsers
        2. AXFocused + keyboard typing — fallback when mouse coords unavailable
        3. AXValue set — last resort for native apps
        """
        element = field.element_ref
        import time

        if self._reader.click_element(element):
            time.sleep(0.15)
            self._reader.type_text(value)
            return True

        if self._reader.set_focus(element):
            time.sleep(0.1)
            self._reader.type_text(value)
            return True

        logger.debug("click and set_focus both failed, trying AXValue fallback")
        if self._reader.focus_element(element) and self._reader.set_value(element, value):
            return True

        return False

    def _fill_textarea(self, field: DetectedField, value: str) -> bool:
        """Fill a text area field."""
        element = field.element_ref
        import time

        if self._reader.click_element(element):
            time.sleep(0.15)
            self._reader.type_text(value)
            return True

        if self._reader.set_focus(element):
            time.sleep(0.1)
            self._reader.type_text(value)
            return True

        logger.debug("click and set_focus both failed for textarea, trying AXValue fallback")
        if self._reader.focus_element(element) and self._reader.set_value(element, value):
            return True

        return False

    def _fill_dropdown(self, field: DetectedField, value: str) -> bool:
        """Fill a dropdown/select field by selecting an option."""
        element = field.element_ref

        if not self._reader.click_element(element):
            return False

        import time

        time.sleep(0.3)

        children = self._reader.get_children(element)
        for child in children:
            child_value = self._reader.get_attribute(child, "AXValue")
            if child_value and str(child_value).lower() == value.lower():
                return self._reader.click_element(child)

            child_title = self._reader.get_attribute(child, "AXTitle")
            if child_title and str(child_title).lower() == value.lower():
                return self._reader.click_element(child)

        logger.warning("Could not find option '%s' in dropdown", value)
        return False

    def _fill_checkbox(self, field: DetectedField, value: str) -> bool:
        """Fill a checkbox field."""
        element = field.element_ref

        current_state = self._reader.get_attribute(element, "AXValue")
        should_check = value.lower() in ("true", "yes", "1", "checked")

        if bool(current_state) != should_check:
            return self._reader.click_element(element)

        return True

    def _fill_radio(self, field: DetectedField, value: str) -> bool:
        """Fill a radio button field."""
        element = field.element_ref

        if value.lower() in ("true", "yes", "1", "selected"):
            return self._reader.click_element(element)

        return True

    def fill_all_fields(
        self,
        fields: list[DetectedField],
        values: dict[str, str],
    ) -> tuple[int, int]:
        """Fill all detected fields with the provided values.

        Args:
            fields: List of DetectedField instances to fill.
            values: Dictionary mapping field identifiers/titles to values.

        Returns:
            Tuple of (success_count, failure_count).
        """
        success_count = 0
        failure_count = 0

        for field in fields:
            value = self._find_value_for_field(field, values)
            if value is None:
                logger.info(
                    "No value found for field '%s' (type=%s), skipping",
                    field.title,
                    field.field_type,
                )
                continue

            if self.fill_field(field, value):
                success_count += 1
            else:
                failure_count += 1

        logger.info(
            "Filled %d fields successfully, %d failed",
            success_count,
            failure_count,
        )
        return success_count, failure_count

    def _find_value_for_field(
        self,
        field: DetectedField,
        values: dict[str, str],
    ) -> str | None:
        """Find the appropriate value for a field from the values dict.

        Matching order:
        1. Map to standard field name (e.g. "email", "first_name")
        2. Exact match by title/identifier/description
        3. Match by field type (e.g. EMAIL → values["email"])
        """
        standard_name = self._detector.map_to_standard_field(field)
        if standard_name and standard_name in values:
            return values[standard_name]

        norm_values = {k.strip().lower(): v for k, v in values.items()}

        for attr_name in ("title", "identifier", "description"):
            candidate = getattr(field, attr_name, None)
            if candidate:
                key = candidate.strip().lower()
                if key in norm_values:
                    return norm_values[key]

        # Fallback: match by field type (handles reclassified types like
        # EMAIL/PHONE/URL that don't match standard names)
        type_to_key: dict[FieldType, str] = {
            FieldType.EMAIL: "email",
            FieldType.PHONE: "phone",
            FieldType.URL: "website",
            FieldType.FILE: "resume",
        }
        key = type_to_key.get(field.field_type)
        if key and key in norm_values:
            return norm_values[key]

        return None
