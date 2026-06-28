"""Apply button detection and clicking."""

from __future__ import annotations

import logging
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
        """Find all Apply/Submit buttons in the current window.

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
        self._search_for_buttons(window_element, buttons, depth=0, max_depth=15)
        logger.info("Found %d apply button(s) via accessibility tree", len(buttons))
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
    ) -> None:
        """Recursively search for apply buttons in the accessibility tree."""
        if depth > max_depth:
            return

        try:
            role = self._reader.get_attribute(element, "AXRole")
            text = self._get_element_text(element)

            is_apply = self._is_apply_button(element, text)
            if not is_apply and not self._children_have_apply_text(element):
                children = self._reader.get_children(element)
                for child in children:
                    self._search_for_buttons(child, results, depth + 1, max_depth)
                return

            if not is_apply:
                children = self._reader.get_children(element)
                for child in children:
                    self._search_for_buttons(child, results, depth + 1, max_depth)
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
                self._search_for_buttons(child, results, depth + 1, max_depth)
        except Exception:
            logger.debug("Error searching element at depth %d", depth)

    def _children_have_apply_text(self, element: Any, max_check: int = 5) -> bool:
        """Quick check if any direct child has apply-related text."""
        children = self._reader.get_children(element)
        for child in children[:max_check]:
            text = self._get_element_text(child)
            if any(kw in text for kw in APPLY_KEYWORDS):
                return True
        return False

    def _record_button(
        self, element: Any, role: str | None, results: list[ApplyButton]
    ) -> None:
        """Create an ApplyButton and append to results."""
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

    def _is_apply_button(self, element: Any, text: str | None = None) -> bool:
        """Check if an element is an Apply/Submit button."""
        if text is None:
            text = self._get_element_text(element)

        if any(skip in text for skip in SKIP_KEYWORDS):
            return False

        if any(keyword in text for keyword in APPLY_KEYWORDS):
            return True

        children = self._reader.get_children(element)
        for child in children:
            child_text = self._get_element_text(child)
            if any(keyword in child_text for keyword in APPLY_KEYWORDS):
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
    ) -> bool:
        """Find and click the first apply button.

        Attempts in order:
        1. Accessibility tree search
        2. OCR (Apple Vision) as fallback

        All clicks use real mouse events (CGEvent) at screen coordinates.

        Args:
            window_element: The window to search. If None, uses focused window.

        Returns:
            True if an apply button was found and clicked, False otherwise.
        """
        buttons = self.find_apply_buttons(window_element)
        if buttons:
            return self.click_button(buttons[0])

        logger.info("Accessibility tree found no buttons, trying OCR fallback...")
        return self._click_by_ocr(window_element)

    def _click_by_ocr(self, window_element: Any | None = None) -> bool:
        """Use Apple Vision OCR to find and click 'Apply' text on screen."""
        for keyword in APPLY_KEYWORDS:
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
