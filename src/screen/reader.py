"""DOM-based screen reader using Playwright CDP connection."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScreenReaderError(Exception):
    pass


class ScreenReader:
    """Reads the current browser page via CDP connection."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    async def connect(self, endpoint_url: str = "http://localhost:9222") -> None:
        """Connect to a running browser via CDP."""
        from playwright.async_api import async_playwright

        if self._browser is not None:
            return

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(endpoint_url)

            contexts = self._browser.contexts
            context = contexts[0] if contexts else await self._browser.new_context()

            pages = context.pages
            if pages:
                self._page = pages[0]
                logger.info("Connected to page: %s", self._page.url)
            else:
                self._page = await context.new_page()

        except Exception as e:
            raise ScreenReaderError(f"Failed to connect to browser: {e}") from e

    async def get_page(self) -> Any:
        if self._page is None or self._page.is_closed():
            await self.connect()
        if self._page is None:
            raise ScreenReaderError("No page available")
        return self._page

    async def url(self) -> str:
        page = await self.get_page()
        return page.url

    async def title(self) -> str:
        page = await self.get_page()
        return await page.title()

    async def content(self) -> str:
        page = await self.get_page()
        return await page.content()

    async def visible_text(self) -> str:
        page = await self.get_page()
        return await page.evaluate("() => document.body?.innerText || ''")

    async def eval(self, expression: str) -> Any:
        page = await self.get_page()
        return await page.evaluate(expression)

    async def query_all(self, selector: str) -> list[Any]:
        page = await self.get_page()
        return await page.query_selector_all(selector)

    async def query(self, selector: str) -> Any | None:
        page = await self.get_page()
        return await page.query_selector(selector)

    async def click(self, selector: str) -> None:
        page = await self.get_page()
        await page.click(selector)

    async def fill(self, selector: str, value: str) -> None:
        page = await self.get_page()
        await page.fill(selector, value)

    async def select(self, selector: str, label: str) -> None:
        page = await self.get_page()
        await page.select_option(selector, label=label)

    async def check(self, selector: str, checked: bool = True) -> None:
        page = await self.get_page()
        await page.set_checked(selector, checked)

    async def upload(self, selector: str, path: str) -> None:
        page = await self.get_page()
        await page.set_input_files(selector, path)

    async def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        page = await self.get_page()
        await page.type(selector, text, delay=delay)

    async def scroll_to(self, selector: str) -> None:
        page = await self.get_page()
        await page.evaluate(
            f"document.querySelector('{selector}')?.scrollIntoView({{behavior: 'smooth'}})"
        )

    async def wait_for(self, selector: str, timeout: int = 5000) -> Any | None:
        page = await self.get_page()
        return await page.wait_for_selector(selector, timeout=timeout)

    async def screenshot(self, path: str) -> None:
        page = await self.get_page()
        await page.screenshot(path=path, full_page=True)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
            self._playwright = None