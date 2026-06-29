"""Apply/submit button finder using DOM selectors."""

from __future__ import annotations

import logging

from src.screen.models import ApplyButton
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

APPLY_SELECTORS = [
    "button:has-text('Apply')",
    "button:has-text('Apply Now')",
    "button:has-text('Easy Apply')",
    "button:has-text('Quick Apply')",
    "a:has-text('Apply')",
    "a:has-text('Apply Now')",
    "[data-testid*='apply']",
    "[class*='apply']",
    "input[type='submit'][value*='Apply']",
]

SUBMIT_SELECTORS = [
    "button[type='submit']",
    "button:has-text('Submit')",
    "button:has-text('Submit Application')",
    "button:has-text('Send')",
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Review')",
    "button:has-text('Finish')",
    "button:has-text('Done')",
    "button:has-text('Save')",
    "input[type='submit']",
    "a:has-text('Submit')",
    "[data-testid*='submit']",
    "[class*='submit']",
]


class ApplyButtonFinder:
    def __init__(self, reader: ScreenReader) -> None:
        self._reader = reader

    async def find_apply_buttons(self) -> list[ApplyButton]:
        """Find apply buttons on the current page."""
        return await self._find_buttons(APPLY_SELECTORS, "apply")

    async def find_submit_buttons(self) -> list[ApplyButton]:
        """Find submit buttons on the current page."""
        return await self._find_buttons(SUBMIT_SELECTORS, "submit")

    async def _find_buttons(self, selectors: list[str], label: str) -> list[ApplyButton]:
        buttons: list[ApplyButton] = []

        for selector in selectors:
            try:
                elements = await self._reader.query_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    visible = await el.is_visible()
                    if visible and text and text.strip():
                        buttons.append(
                            ApplyButton(
                                role="button",
                                title=text.strip(),
                                description="",
                                element_ref=selector,  # Store selector for clicking
                            )
                        )
            except Exception as e:
                logger.debug("Selector %s failed: %s", selector, e)

        # Remove duplicates by title
        seen = set()
        unique = []
        for btn in buttons:
            if btn.title.lower() not in seen:
                seen.add(btn.title.lower())
                unique.append(btn)

        logger.info("Found %d %s button(s)", len(unique), label)
        return unique

    async def click_button(self, button: ApplyButton) -> bool:
        """Click a button by its stored selector."""
        if not button.element_ref:
            return False

        try:
            await self._reader.click(button.element_ref)
            logger.info("Clicked button: '%s'", button.title)
            return True
        except Exception as e:
            logger.warning("Failed to click button '%s': %s", button.title, e)
            return False

    async def find_and_click_apply(self) -> bool:
        """Find and click the first apply button."""
        buttons = await self.find_apply_buttons()
        if buttons:
            return await self.click_button(buttons[0])

        # Fallback: scroll and try again
        await self._reader.eval("window.scrollTo(0, document.body.scrollHeight)")
        buttons = await self.find_apply_buttons()
        if buttons:
            return await self.click_button(buttons[0])

        logger.warning("No apply button found")
        return False

    async def find_and_click_submit(self) -> bool:
        """Find and click the first submit button."""
        buttons = await self.find_submit_buttons()
        if buttons:
            return await self.click_button(buttons[0])

        logger.warning("No submit button found")
        return False

    async def has_apply_button(self) -> bool:
        """Check if page has an apply button."""
        buttons = await self.find_apply_buttons()
        return len(buttons) > 0
