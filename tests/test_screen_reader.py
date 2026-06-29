"""Tests for DOM-based screen reader."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.screen.reader import ScreenReader, ScreenReaderError


def _make_page(**kwargs):
    from unittest.mock import AsyncMock

    page = MagicMock(**kwargs)
    page.is_closed.return_value = False
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.select_option = AsyncMock()
    page.set_checked = AsyncMock()
    page.type = AsyncMock()
    page.evaluate = AsyncMock()
    page.screenshot = AsyncMock()
    page.title = AsyncMock()
    page.content = AsyncMock()
    page.query_selector_all = AsyncMock()
    page.query_selector = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.set_input_files = AsyncMock()
    return page


class TestScreenReader:
    @pytest.mark.asyncio
    async def test_initialization(self):
        reader = ScreenReader()
        assert reader._playwright is None
        assert reader._browser is None
        assert reader._page is None

    @pytest.mark.asyncio
    async def test_connect_success(self):
        mock_page = _make_page(url="https://example.com")
        mock_context = MagicMock()
        mock_context.pages = [mock_page]
        mock_browser = MagicMock()
        mock_browser.contexts = [mock_context]
        mock_pw = AsyncMock()
        mock_pw.chromium.connect_over_cdp = AsyncMock(return_value=mock_browser)
        mock_pw_instance = MagicMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_pw)

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_instance):
            reader = ScreenReader()
            await reader.connect()

            assert reader._browser is not None
            assert reader._page is not None

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        reader = ScreenReader()
        reader._browser = MagicMock()
        await reader.connect()
        assert reader._browser is not None

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        mock_pw_instance = MagicMock()
        mock_pw_instance.start = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("playwright.async_api.async_playwright", return_value=mock_pw_instance):
            reader = ScreenReader()
            with pytest.raises(ScreenReaderError, match="Failed to connect to browser"):
                await reader.connect()

    @pytest.mark.asyncio
    async def test_get_page_returns_page(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        page = await reader.get_page()
        assert page == mock_page

    @pytest.mark.asyncio
    async def test_get_page_reconnects_when_closed(self):
        reader = ScreenReader()
        reader.connect = AsyncMock()
        mock_page = _make_page()
        mock_page.is_closed.return_value = True
        reader._page = mock_page

        page = await reader.get_page()
        assert page == mock_page
        reader.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_page_raises_when_no_page(self):
        reader = ScreenReader()
        reader.connect = AsyncMock()
        reader._page = None

        with pytest.raises(ScreenReaderError, match="No page available"):
            await reader.get_page()

    @pytest.mark.asyncio
    async def test_url(self):
        reader = ScreenReader()
        mock_page = _make_page(url="https://example.com/jobs")
        reader._page = mock_page

        url = await reader.url()
        assert url == "https://example.com/jobs"

    @pytest.mark.asyncio
    async def test_title(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.title = AsyncMock(return_value="Jobs Page")
        reader._page = mock_page

        title = await reader.title()
        assert title == "Jobs Page"

    @pytest.mark.asyncio
    async def test_content(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.content = AsyncMock(return_value="<html></html>")
        reader._page = mock_page

        content = await reader.content()
        assert content == "<html></html>"

    @pytest.mark.asyncio
    async def test_visible_text(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.evaluate = AsyncMock(return_value="Some visible text")
        reader._page = mock_page

        text = await reader.visible_text()
        assert text == "Some visible text"
        mock_page.evaluate.assert_called_once_with("() => document.body?.innerText || ''")

    @pytest.mark.asyncio
    async def test_eval(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.evaluate = AsyncMock(return_value=42)
        reader._page = mock_page

        result = await reader.eval("1 + 1")
        assert result == 42

    @pytest.mark.asyncio
    async def test_query_all(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.query_selector_all = AsyncMock(return_value=["el1", "el2"])
        reader._page = mock_page

        elements = await reader.query_all("button")
        assert elements == ["el1", "el2"]

    @pytest.mark.asyncio
    async def test_query_found(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.query_selector = AsyncMock(return_value=MagicMock())
        reader._page = mock_page

        elem = await reader.query("#submit")
        assert elem is not None

    @pytest.mark.asyncio
    async def test_query_not_found(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.query_selector = AsyncMock(return_value=None)
        reader._page = mock_page

        elem = await reader.query("#nonexistent")
        assert elem is None

    @pytest.mark.asyncio
    async def test_click(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.click("#btn")
        mock_page.click.assert_called_once_with("#btn")

    @pytest.mark.asyncio
    async def test_fill(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.fill("#email", "test@example.com")
        mock_page.fill.assert_called_once_with("#email", "test@example.com")

    @pytest.mark.asyncio
    async def test_select(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.select("#level", "Senior")
        mock_page.select_option.assert_called_once_with("#level", label="Senior")

    @pytest.mark.asyncio
    async def test_check_true(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.check("#agree", True)
        mock_page.set_checked.assert_called_once_with("#agree", True)

    @pytest.mark.asyncio
    async def test_check_false(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.check("#agree", False)
        mock_page.set_checked.assert_called_once_with("#agree", False)

    @pytest.mark.asyncio
    async def test_upload(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.upload("#resume", "/path/to/resume.pdf")
        mock_page.set_input_files.assert_called_once_with("#resume", "/path/to/resume.pdf")

    @pytest.mark.asyncio
    async def test_type_text(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.type_text("#input", "hello")
        mock_page.type.assert_called_once_with("#input", "hello", delay=50)

    @pytest.mark.asyncio
    async def test_scroll_to(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.scroll_to("#target")
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for(self):
        reader = ScreenReader()
        mock_page = _make_page()
        mock_page.wait_for_selector = AsyncMock(return_value=MagicMock())
        reader._page = mock_page

        result = await reader.wait_for("#load", timeout=3000)
        assert result is not None
        mock_page.wait_for_selector.assert_called_once_with("#load", timeout=3000)

    @pytest.mark.asyncio
    async def test_screenshot(self):
        reader = ScreenReader()
        mock_page = _make_page()
        reader._page = mock_page

        await reader.screenshot("/tmp/shot.png")
        mock_page.screenshot.assert_called_once_with(path="/tmp/shot.png", full_page=True)

    @pytest.mark.asyncio
    async def test_close(self):
        reader = ScreenReader()
        mock_browser = AsyncMock()
        reader._browser = mock_browser
        reader._page = MagicMock()
        reader._playwright = MagicMock()

        await reader.close()
        mock_browser.close.assert_awaited_once()
        assert reader._browser is None
        assert reader._page is None
        assert reader._playwright is None
