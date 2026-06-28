"""Apply button detection and clicking."""

from __future__ import annotations

import logging
import time
from typing import Any

from src.screen.models import ApplyButton
from src.screen.reader import ScreenReader

logger = logging.getLogger(__name__)

# Keywords that indicate an Apply/Submit button
APPLY_KEYWORDS = [
    "apply",
    "submit",
    "send",
    "apply now",
    "easy apply",
    "quick apply",
    "apply for this job",
    "apply to this role",
    "start application",
    "begin application",
    "continue",
    "next",
]

# Keywords that indicate a Submit button on the application form itself
SUBMIT_KEYWORDS = [
    "submit",
    "send",
    "submit application",
    "send application",
    "apply",
    "next",
    "continue",
    "review",
    "finish",
    "done",
    "save",
    "save & continue",
    "save and continue",
    "submit form",
]

# Keywords that indicate navigation buttons to skip
SKIP_KEYWORDS = [
    "back",
    "previous",
    "cancel",
    "close",
    "dismiss",
    "skip",
    "later",
    "not now",
]


class ApplyButtonFinder:
    """Finds and clicks Apply/Submit buttons in the current window.

    Uses a hybrid approach:
    1. Accessibility tree search for known button roles + AXPress
    2. Real mouse clicks via CGEvent at element screen coordinates
    3. OCR fallback via Apple Vision when the accessibility tree
       doesn't expose the button
    """

    def __init__(self, reader: ScreenReader) -> None:
        """Initialize the button finder.

        Args:
            reader: The ScreenReader instance for accessing the UI.
        """
        self._reader = reader

    def find_apply_buttons(
        self,
        window_element: Any | None = None,
    ) -> list[ApplyButton]:
        """Find all Apply buttons in the current window.

        Args:
            window_element: The window to search. If None, uses focused window.

        Returns:
            List of detected ApplyButton instances.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()

        if window_element is None:
            logger.warning("No focused window found")
            return []

        buttons: list[ApplyButton] = []
        self._search_for_buttons(
            window_element, buttons, depth=0, max_depth=15, keywords=APPLY_KEYWORDS,
        )
        logger.info("Found %d apply button(s) via accessibility tree", len(buttons))
        return buttons

    def find_submit_buttons(
        self,
        window_element: Any | None = None,
    ) -> list[ApplyButton]:
        """Find all Submit buttons on the current application form.

        Uses SUBMIT_KEYWORDS which includes submit, send, next, continue, etc.
        This is called AFTER the apply button has been clicked and the form
        is visible.

        Args:
            window_element: The window to search. If None, uses focused window.

        Returns:
            List of detected ApplyButton instances.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()

        if window_element is None:
            logger.warning("No focused window found")
            return []

        buttons: list[ApplyButton] = []
        self._search_for_buttons(
            window_element, buttons, depth=0, max_depth=15, keywords=SUBMIT_KEYWORDS,
        )
        logger.info("Found %d submit button(s) via accessibility tree", len(buttons))
        return buttons

    def _get_element_text(self, element: Any) -> str:
        """Get combined text content from an element's accessible attributes."""
        parts = [
            str(self._reader.get_attribute(element, "AXTitle") or ""),
            str(self._reader.get_attribute(element, "AXDescription") or ""),
            str(self._reader.get_attribute(element, "AXValue") or ""),
        ]
        return " ".join(p.strip() for p in parts if p.strip()).lower()

    def _search_for_buttons(
        self,
        element: Any,
        results: list[ApplyButton],
        depth: int,
        max_depth: int,
        keywords: list[str] | None = None,
    ) -> None:
        """Recursively search for buttons in the accessibility tree.

        Args:
            element: The element to search.
            results: List to append found buttons to.
            depth: Current recursion depth.
            max_depth: Maximum recursion depth.
            keywords: Keywords to match against element text. If None, uses APPLY_KEYWORDS.
        """
        if depth > max_depth:
            return

        if keywords is None:
            keywords = APPLY_KEYWORDS

        try:
            role = self._reader.get_attribute(element, "AXRole")
            text = self._get_element_text(element)

            is_match = self._is_match(element, text, keywords)
            if not is_match and not self._children_have_text(element, keywords):
                children = self._reader.get_children(element)
                for child in children:
                    self._search_for_buttons(child, results, depth + 1, max_depth, keywords)
                return

            if not is_match:
                children = self._reader.get_children(element)
                for child in children:
                    self._search_for_buttons(child, results, depth + 1, max_depth, keywords)
                return

            if role in ("AXButton", "AXLink", "AXMenuItem"):
                self._record_button(element, role, results)
                return

            actions = self._reader.action_names(element)
            if "AXPress" in actions:
                self._record_button(element, role, results)
                return

            children = self._reader.get_children(element)
            for child in children:
                self._search_for_buttons(child, results, depth + 1, max_depth, keywords)
        except Exception:
            logger.debug("Error searching element at depth %d", depth)

    def _children_have_text(
        self, element: Any, keywords: list[str], max_check: int = 5
    ) -> bool:
        """Quick check if any direct child has matching text."""
        children = self._reader.get_children(element)
        for child in children[:max_check]:
            text = self._get_element_text(child)
            if any(kw in text for kw in keywords):
                return True
        return False

    def _record_button(
        self, element: Any, role: str | None, results: list[ApplyButton]
    ) -> None:
        """Create an ApplyButton and append to results if element has a valid screen position.

        Elements without screen coordinates (AXPosition) are invisible/off-screen
        and cannot be clicked via CGEvent. Skipping them forces the OCR fallback
        which is more reliable for web content.
        """
        pos = self._reader.get_element_position(element)
        size = self._reader.get_element_size(element)
        if not pos or not size or size[0] <= 0 or size[1] <= 0:
            logger.debug(
                "Skipping invisible element (role=%s, no valid position/size)", role
            )
            return

        button = ApplyButton(
            role=role or "AXButton",
            title=str(self._reader.get_attribute(element, "AXTitle") or ""),
            description=str(self._reader.get_attribute(element, "AXDescription") or ""),
            element_ref=element,
        )
        results.append(button)
        logger.debug(
            "Found apply button: title='%s', desc='%s'",
            button.title,
            button.description,
        )

    def _is_match(
        self, element: Any, text: str | None = None, keywords: list[str] | None = None
    ) -> bool:
        """Check if an element matches the given keywords.

        Args:
            element: The element to check.
            text: Pre-computed element text (computed from AXTitle/AXDescription/AXValue).
            keywords: Keywords to match. If None, uses APPLY_KEYWORDS.

        Returns:
            True if the element matches the keywords (and doesn't match SKIP_KEYWORDS).
        """
        if text is None:
            text = self._get_element_text(element)
        if keywords is None:
            keywords = APPLY_KEYWORDS

        if any(skip in text for skip in SKIP_KEYWORDS):
            return False

        if any(keyword in text for keyword in keywords):
            return True

        children = self._reader.get_children(element)
        for child in children:
            child_text = self._get_element_text(child)
            if any(keyword in child_text for keyword in keywords):
                return True

        return False

    def click_button(self, button: ApplyButton) -> bool:
        """Click an apply button using a real mouse event at its screen position.

        Uses CGEvent (real mouse click) at the element's screen coordinates,
        which reliably works in web browsers unlike AXPress.

        Args:
            button: The ApplyButton to click.

        Returns:
            True if the click succeeded, False otherwise.
        """
        if button.element_ref is None:
            logger.error("Button has no element reference")
            return False

        logger.info("Clicking apply button: '%s' (via CGEvent)", button.title)

        pos = self._reader.get_element_position(button.element_ref)
        size = self._reader.get_element_size(button.element_ref)
        if pos and size:
            center_x = pos[0] + size[0] / 2
            center_y = pos[1] + size[1] / 2
            logger.info("  → screen coords: (%.0f, %.0f)", center_x, center_y)
            return self._reader.mouse_click_at(center_x, center_y)

        logger.warning("  → no screen position, falling back to AXPress")
        return self._reader.perform_action(button.element_ref, "AXPress")

    def find_and_click_apply(
        self,
        window_element: Any | None = None,
        max_scrolls: int = 5,
        scroll_pause: float = 0.5,
    ) -> bool:
        """Find and click the first apply button, scrolling to find off-screen buttons.

        Attempts in order, with scrolling between each cycle:
        1. Accessibility tree search
        2. OCR (Apple Vision) fallback
        3. Scroll down → repeat 1 + 2 for max_scrolls attempts

        All clicks use real mouse events (CGEvent) at screen coordinates.

        Args:
            window_element: The window to search. If None, uses focused window.
            max_scrolls: Max number of scroll attempts to reveal off-screen content.
            scroll_pause: Seconds to wait after each scroll.

        Returns:
            True if an apply button was found and clicked, False otherwise.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()
        if window_element is None:
            logger.warning("No focused window found")
            return False

        for attempt in range(max_scrolls):
            buttons = self.find_apply_buttons(window_element)
            if buttons:
                return self.click_button(buttons[0])

            if self._click_by_ocr(window_element):
                return True

            if attempt < max_scrolls - 1:
                logger.info(
                    "No apply button visible (attempt %d/%d), scrolling down...",
                    attempt + 1, max_scrolls,
                )
                if not self._reader.scroll_down(window_element):
                    logger.info("Cannot scroll further")
                    break
                time.sleep(scroll_pause)

        logger.warning("No apply button found after %d scroll attempts", max_scrolls)
        return False

    def find_and_click_submit(
        self,
        window_element: Any | None = None,
        max_scrolls: int = 3,
        scroll_pause: float = 0.5,
    ) -> bool:
        """Find and click the submit button on the application form.

        Uses SUBMIT_KEYWORDS to find the button. Unlike find_and_click_apply,
        this searches for form submission buttons (Submit, Send, Next, etc.)
        rather than initial apply buttons.

        Attempts in order, with scrolling between each cycle:
        1. Accessibility tree search for submit buttons
        2. OCR fallback using SUBMIT_KEYWORDS
        3. Scroll down → repeat for max_scrolls attempts

        Args:
            window_element: The window to search. If None, uses focused window.
            max_scrolls: Max scroll attempts to reveal off-screen content.
            scroll_pause: Seconds to wait after each scroll.

        Returns:
            True if a submit button was found and clicked, False otherwise.
        """
        if window_element is None:
            window_element = self._reader.get_focused_window()
        if window_element is None:
            logger.warning("No focused window found")
            return False

        for attempt in range(max_scrolls):
            buttons = self.find_submit_buttons(window_element)
            if buttons:
                return self.click_button(buttons[0])

            if self._click_by_ocr(window_element, keywords=SUBMIT_KEYWORDS):
                return True

            if attempt < max_scrolls - 1:
                logger.info(
                    "No submit button visible (attempt %d/%d), scrolling down...",
                    attempt + 1, max_scrolls,
                )
                if not self._reader.scroll_down(window_element):
                    break
                time.sleep(scroll_pause)

        logger.warning("No submit button found after %d scroll attempts", max_scrolls)
        return False

    def _click_by_ocr(
        self,
        window_element: Any | None = None,
        keywords: list[str] | None = None,
    ) -> bool:
        """Use Apple Vision OCR to find and click matching text on screen.

        Args:
            window_element: The window to search. If None, uses focused window.
            keywords: Keywords to search for. If None, uses APPLY_KEYWORDS.
        """
        if keywords is None:
            keywords = APPLY_KEYWORDS
        for keyword in keywords:
            matches = self._reader.find_text_on_screen(keyword, window_element)
            if matches:
                x, y, text = matches[0]
                logger.info(
                    "OCR found '%s' → clicking at (%.0f, %.0f)",
                    text.strip(), x, y,
                )
                return self._reader.mouse_click_at(x, y)
        logger.warning("OCR fallback: no apply text found on screen")
        return False

    def has_apply_button(self, window_element: Any | None = None) -> bool:
        """Check if the current window has an apply button without clicking it."""
        buttons = self.find_apply_buttons(window_element)
        if buttons:
            return True

        for keyword in APPLY_KEYWORDS:
            if self._reader.find_text_on_screen(keyword, window_element):
                return True
        return False
