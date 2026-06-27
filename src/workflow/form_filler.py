import logging

from src.browser.engine import BrowserEngine
from src.models.forms import FormField

logger = logging.getLogger("job-bot.form_filler")


class FormFillError(Exception):
    pass


class FormFiller:
    def __init__(self, browser: BrowserEngine) -> None:
        self._browser = browser

    async def fill_fields(self, fields: list[FormField]) -> None:
        errors: list[str] = []
        for field in fields:
            try:
                await self._fill_one(field)
            except Exception as e:
                msg = f"Failed to fill {field.selector} ({field.field_type}): {e}"
                errors.append(msg)
                logger.warning(msg)
        if errors:
            raise FormFillError("; ".join(errors))

    async def _fill_one(self, field: FormField) -> None:
        dispatch = {
            "text": self._fill_text,
            "select": self._fill_select,
            "file": self._fill_file,
            "checkbox": self._fill_checkbox,
        }
        handler = dispatch.get(field.field_type)
        if handler is None:
            raise FormFillError(f"Unsupported field type: {field.field_type}")
        await handler(field)

    async def _fill_text(self, field: FormField) -> None:
        if not isinstance(field.value, str):
            raise FormFillError("Text field value must be a string")
        await self._browser.fill(field.selector, field.value)

    async def _fill_select(self, field: FormField) -> None:
        if not isinstance(field.value, str):
            raise FormFillError("Select field value must be a string")
        await self._browser.select_option(field.selector, field.value)

    async def _fill_file(self, field: FormField) -> None:
        if not isinstance(field.value, str):
            raise FormFillError("File field value must be a string path")
        await self._browser.upload_file(field.selector, field.value)

    async def _fill_checkbox(self, field: FormField) -> None:
        if not isinstance(field.value, bool):
            raise FormFillError("Checkbox field value must be a boolean")
        await self._browser.set_checked(field.selector, field.value)
