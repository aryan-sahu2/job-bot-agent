"""DOM-based form filler using Playwright."""

from __future__ import annotations

import logging

from src.screen.form_detector import FormDetector
from src.screen.models import DetectedField, FieldType
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)


class FormFiller:
    def __init__(self, reader: ScreenReader, detector: FormDetector) -> None:
        self._reader = reader
        self._detector = detector

    async def fill_field(self, field: DetectedField, value: str) -> bool:
        if not field.identifier:
            logger.error("Field '%s' has no selector", field.title)
            return False

        logger.info("Filling field '%s' (type=%s)", field.title, field.field_type)

        try:
            match field.field_type:
                case (
                    FieldType.TEXT
                    | FieldType.EMAIL
                    | FieldType.PHONE
                    | FieldType.NAME
                    | FieldType.URL
                    | FieldType.DATE
                ):
                    await self._reader.fill(field.identifier, value)
                case FieldType.TEXTAREA:
                    await self._reader.fill(field.identifier, value)
                case FieldType.SELECT:
                    await self._reader.select(field.identifier, value)
                case FieldType.CHECKBOX:
                    should_check = value.lower() in ("true", "yes", "1", "checked", "on")
                    await self._reader.check(field.identifier, should_check)
                case FieldType.RADIO:
                    should_select = value.lower() in ("true", "yes", "1", "selected")
                    if should_select:
                        await self._reader.click(field.identifier)
                case FieldType.FILE:
                    await self._reader.upload(field.identifier, value)
                case _:
                    await self._reader.fill(field.identifier, value)

            logger.info("Filled field '%s'", field.title)
            return True

        except Exception as e:
            logger.warning("Failed to fill field '%s': %s", field.title, e)
            return False

    async def fill_all_fields(
        self, fields: list[DetectedField], values: dict[str, str]
    ) -> tuple[int, int]:
        success = 0
        failure = 0

        for field in fields:
            value = self._find_value_for_field(field, values)
            if value is None:
                logger.info("No value for field '%s', skipping", field.title)
                continue

            if await self.fill_field(field, value):
                success += 1
            else:
                failure += 1

        logger.info("Filled %d fields, %d failed", success, failure)
        return success, failure

    def _find_value_for_field(self, field: DetectedField, values: dict[str, str]) -> str | None:
        # 1. Standard field mapping
        standard = self._detector.map_to_standard_field(field)
        if standard and standard in values:
            return values[standard]

        # 2. Exact match by title/identifier
        norm = {k.strip().lower(): v for k, v in values.items()}
        for attr in ("title", "identifier", "description"):
            key = getattr(field, attr, "")
            if key:
                lookup = key.strip().lower()
                if lookup in norm:
                    return norm[lookup]

        # 3. Type-based fallback
        type_map = {
            FieldType.EMAIL: "email",
            FieldType.PHONE: "phone",
            FieldType.URL: "website",
            FieldType.FILE: "resume",
        }
        key = type_map.get(field.field_type)
        if key and key in norm:
            return norm[key]

        return None
