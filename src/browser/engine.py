from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

from src.config.loader import BrowserConfig


class BrowserError(Exception):
    pass


class BrowserEngine:
    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> None:
        try:
            p = await async_playwright().start()
            self._browser = await p.chromium.launch(headless=self._config.headless)
            self._context = await self._browser.new_context(
                viewport={
                    "width": self._config.viewport.width,
                    "height": self._config.viewport.height,
                },
            )
            self._page = await self._context.new_page()
        except Exception as e:
            raise BrowserError(f"Failed to launch browser: {e}") from e

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None

    async def navigate(self, url: str) -> None:
        page = self._require_page()
        try:
            await page.goto(url, timeout=self._config.timeout, wait_until="domcontentloaded")
        except Exception as e:
            raise BrowserError(f"Failed to navigate to {url}: {e}") from e

    async def click(self, selector: str) -> None:
        page = self._require_page()
        try:
            await page.click(selector)
        except Exception as e:
            raise BrowserError(f"Failed to click {selector}: {e}") from e

    async def fill(self, selector: str, value: str) -> None:
        page = self._require_page()
        try:
            await page.fill(selector, value)
        except Exception as e:
            raise BrowserError(f"Failed to fill {selector}: {e}") from e

    async def upload_file(self, selector: str, file_path: str) -> None:
        page = self._require_page()
        path = Path(file_path)
        if not path.exists():
            raise BrowserError(f"File not found: {file_path}")
        try:
            await page.set_input_files(selector, str(path))
        except Exception as e:
            raise BrowserError(f"Failed to upload {file_path} to {selector}: {e}") from e

    async def scroll(self, selector: str | None = None) -> None:
        page = self._require_page()
        try:
            if selector:
                await page.evaluate(f"document.querySelector('{selector}')?.scrollIntoView()")
            else:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception as e:
            raise BrowserError(f"Failed to scroll: {e}") from e

    async def wait_for(self, selector: str, timeout: int | None = None) -> None:
        page = self._require_page()
        try:
            await page.wait_for_selector(
                selector,
                timeout=timeout or self._config.timeout,
            )
        except Exception as e:
            raise BrowserError(f"Failed waiting for {selector}: {e}") from e

    async def screenshot(self, path: str) -> None:
        page = self._require_page()
        try:
            await page.screenshot(path=path, full_page=True)
        except Exception as e:
            raise BrowserError(f"Failed to save screenshot to {path}: {e}") from e

    async def __aenter__(self) -> "BrowserEngine":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def _require_page(self) -> Page:
        if self._page is None:
            raise BrowserError("Browser not started. Call start() first.")
        return self._page
