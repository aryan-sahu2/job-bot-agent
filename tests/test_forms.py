from unittest.mock import AsyncMock

import pytest

from src.browser.engine import BrowserEngine
from src.config.loader import BrowserConfig
from src.models.forms import FormField
from src.workflow.form_filler import FormFiller, FormFillError


@pytest.fixture
def config() -> BrowserConfig:
    return BrowserConfig(headless=True, timeout=15000)


class TestBrowserSelectOption:
    @pytest.mark.asyncio
    async def test_select_option_on_select_element(self, config: BrowserConfig):
        html = (
            "<html><body><select id='test'>"
            "<option value='a'>Option A</option>"
            "<option value='b'>Option B</option>"
            "</select></body></html>"
        )
        async with BrowserEngine(config) as engine:
            await engine.navigate(f"data:text/html,{html}")
            await engine.select_option("#test", "Option B")
            result = await engine.evaluate("document.querySelector('#test').value")
            assert result == "b"

    @pytest.mark.asyncio
    async def test_select_option_raises_on_missing_element(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            with pytest.raises(Exception):
                await engine.select_option("#nonexistent", "value")


class TestBrowserSetChecked:
    @pytest.mark.asyncio
    async def test_check_checkbox(self, config: BrowserConfig):
        html = "<html><body><input type='checkbox' id='test'></body></html>"
        async with BrowserEngine(config) as engine:
            await engine.navigate(f"data:text/html,{html}")
            await engine.set_checked("#test", True)
            result = await engine.evaluate("document.querySelector('#test').checked")
            assert result is True

    @pytest.mark.asyncio
    async def test_uncheck_checkbox(self, config: BrowserConfig):
        html = "<html><body><input type='checkbox' id='test' checked></body></html>"
        async with BrowserEngine(config) as engine:
            await engine.navigate(f"data:text/html,{html}")
            await engine.set_checked("#test", False)
            result = await engine.evaluate("document.querySelector('#test').checked")
            assert result is False

    @pytest.mark.asyncio
    async def test_set_checked_raises_on_missing_element(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            with pytest.raises(Exception):
                await engine.set_checked("#nonexistent", True)


class TestFormFiller:
    @pytest.mark.asyncio
    async def test_fill_text_field(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#name", field_type="text", value="Jane")]
        await filler.fill_fields(fields)
        browser.fill.assert_awaited_once_with("#name", "Jane")

    @pytest.mark.asyncio
    async def test_fill_select_field(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#country", field_type="select", value="US")]
        await filler.fill_fields(fields)
        browser.select_option.assert_awaited_once_with("#country", "US")

    @pytest.mark.asyncio
    async def test_fill_file_field(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#resume", field_type="file", value="/path/to/resume.pdf")]
        await filler.fill_fields(fields)
        browser.upload_file.assert_awaited_once_with("#resume", "/path/to/resume.pdf")

    @pytest.mark.asyncio
    async def test_fill_checkbox_checked(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#agree", field_type="checkbox", value=True)]
        await filler.fill_fields(fields)
        browser.set_checked.assert_awaited_once_with("#agree", True)

    @pytest.mark.asyncio
    async def test_fill_checkbox_unchecked(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#agree", field_type="checkbox", value=False)]
        await filler.fill_fields(fields)
        browser.set_checked.assert_awaited_once_with("#agree", False)

    @pytest.mark.asyncio
    async def test_fill_multiple_fields(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [
            FormField(selector="#name", field_type="text", value="Jane"),
            FormField(selector="#country", field_type="select", value="US"),
        ]
        await filler.fill_fields(fields)
        browser.fill.assert_awaited_once_with("#name", "Jane")
        browser.select_option.assert_awaited_once_with("#country", "US")

    @pytest.mark.asyncio
    async def test_unsupported_field_type_raises(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#x", field_type="radio", value="y")]
        with pytest.raises(FormFillError, match="Unsupported field type"):
            await filler.fill_fields(fields)

    @pytest.mark.asyncio
    async def test_raises_on_first_error(self):
        browser = AsyncMock(spec=BrowserEngine)
        browser.fill.side_effect = Exception("input not found")
        filler = FormFiller(browser)
        fields = [
            FormField(selector="#name", field_type="text", value="Jane"),
            FormField(selector="#email", field_type="text", value="j@e.com"),
        ]
        with pytest.raises(FormFillError, match="input not found"):
            await filler.fill_fields(fields)

    @pytest.mark.asyncio
    async def test_text_with_bool_value_raises(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#x", field_type="text", value=True)]
        with pytest.raises(FormFillError, match="Text field value must be a string"):
            await filler.fill_fields(fields)

    @pytest.mark.asyncio
    async def test_checkbox_with_string_value_raises(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        fields = [FormField(selector="#x", field_type="checkbox", value="yes")]
        with pytest.raises(FormFillError, match="Checkbox field value must be a boolean"):
            await filler.fill_fields(fields)

    @pytest.mark.asyncio
    async def test_empty_fields_list(self):
        browser = AsyncMock(spec=BrowserEngine)
        filler = FormFiller(browser)
        await filler.fill_fields([])
        browser.fill.assert_not_called()
        browser.select_option.assert_not_called()
        browser.upload_file.assert_not_called()
        browser.set_checked.assert_not_called()
