import pytest

from src.browser import BrowserEngine
from src.browser.engine import BrowserError
from src.config.loader import BrowserConfig


@pytest.fixture
def config() -> BrowserConfig:
    return BrowserConfig(headless=True, timeout=15000)


class TestBrowserEngine:
    @pytest.mark.asyncio
    async def test_start_and_close(self, config: BrowserConfig):
        engine = BrowserEngine(config)
        await engine.start()
        assert engine._page is not None
        await engine.close()
        assert engine._page is None
        assert engine._browser is None

    @pytest.mark.asyncio
    async def test_context_manager(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            assert engine._page is not None
        assert engine._page is None

    @pytest.mark.asyncio
    async def test_navigate(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            assert engine._page.url == "about:blank"

    @pytest.mark.asyncio
    async def test_click_raises_on_missing_element(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            with pytest.raises(BrowserError):
                await engine.click("#nonexistent")

    @pytest.mark.asyncio
    async def test_fill_raises_on_missing_element(self, config: BrowserConfig):
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            with pytest.raises(BrowserError):
                await engine.fill("#nonexistent", "value")

    @pytest.mark.asyncio
    async def test_operation_before_start_raises(self, config: BrowserConfig):
        engine = BrowserEngine(config)
        with pytest.raises(BrowserError, match="not started"):
            await engine.navigate("about:blank")

    @pytest.mark.asyncio
    async def test_screenshot(self, config: BrowserConfig, tmp_path):
        screenshot_path = tmp_path / "test.png"
        async with BrowserEngine(config) as engine:
            await engine.navigate("about:blank")
            await engine.screenshot(str(screenshot_path))
        assert screenshot_path.exists()
