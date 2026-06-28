"""macOS Accessibility-based screen reader."""

from __future__ import annotations

import logging
import time
from typing import Any

import ApplicationServices as app_services  # noqa: N813

logger = logging.getLogger(__name__)


class ScreenReader:
    """Reads UI elements using macOS Accessibility APIs.

    Requires Accessibility permissions to be granted to the terminal/Python
    process. Can read the focused window, traverse the UI tree, and perform
    actions on elements.
    """

    def __init__(self) -> None:
        """Initialize the screen reader with a system-wide accessibility element."""
        self._system_wide = app_services.AXUIElementCreateSystemWide()

    def get_focused_app(self) -> Any | None:
        """Get the currently focused application's accessibility element."""
        try:
            error, value = app_services.AXUIElementCopyAttributeValue(
                self._system_wide, "AXFocusedApplication", None
            )
            if error == 0:
                return value
            logger.debug(
                "AXFocusedApplication failed (error %d), using CGWindowList fallback",
                error,
            )
            return self._get_focused_app_via_window_list()
        except Exception:
            logger.debug("Exception with AXFocusedApplication, using CGWindowList fallback")
            return self._get_focused_app_via_window_list()

    def _get_focused_app_via_window_list(self) -> Any | None:
        """Get focused app by finding the frontmost window via CGWindowList."""
        try:
            import Quartz

            window_list = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly
                | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID,
            )
            for window in window_list:
                if window.get("kCGWindowLayer", -1) == 0:
                    pid = window.get("kCGWindowOwnerPID")
                    if pid:
                        return app_services.AXUIElementCreateApplication(pid)
        except Exception:
            logger.exception("Exception in CGWindowList fallback")
        return None

    def get_focused_window(self, app_element: Any | None = None) -> Any | None:
        """Get the focused window of the given or focused application."""
        try:
            if app_element is None:
                app_element = self.get_focused_app()
            if app_element is None:
                return None

            error, value = app_services.AXUIElementCopyAttributeValue(
                app_element, "AXFocusedWindow", None
            )
            if error == 0:
                return value
            logger.warning("Failed to get focused window, error code: %d", error)
            return None
        except Exception:
            logger.exception("Exception getting focused window")
            return None

    def get_window_title(self, window_element: Any | None = None) -> str:
        """Get the title of the given or focused window."""
        try:
            if window_element is None:
                window_element = self.get_focused_window()
            if window_element is None:
                return ""

            error, value = app_services.AXUIElementCopyAttributeValue(
                window_element, "AXTitle", None
            )
            if error == 0 and value:
                return str(value)
            return ""
        except Exception:
            logger.exception("Exception getting window title")
            return ""

    def get_window_url(self, window_element: Any | None = None) -> str:
        """Attempt to extract the URL from the focused browser window.

        This works by reading the URL bar value from Chrome/Safari/Firefox
        accessibility trees.
        """
        try:
            if window_element is None:
                window_element = self.get_focused_window()
            if window_element is None:
                return ""

            children = self._get_children(window_element)
            for child in children:
                url = self._extract_url_from_element(child)
                if url:
                    return url
            return ""
        except Exception:
            logger.exception("Exception getting window URL")
            return ""

    def _extract_url_from_element(self, element: Any) -> str:
        """Recursively search for URL-like values in the accessibility tree."""
        try:
            role = self._get_attribute(element, "AXRole")
            value = self._get_attribute(element, "AXValue")

            if role in ("AXTextField", "AXComboBox", "AXURLField") and value:
                val_str = str(value)
                if val_str.startswith(("http://", "https://", "www.")):
                    return val_str

            children = self._get_children(element)
            for child in children:
                result = self._extract_url_from_element(child)
                if result:
                    return result
        except Exception:
            pass
        return ""

    def get_children(self, element: Any) -> list[Any]:
        """Get the direct children of an accessibility element."""
        return self._get_children(element)

    def _get_children(self, element: Any) -> list[Any]:
        """Get children of an accessibility element."""
        try:
            error, value = app_services.AXUIElementCopyAttributeValue(element, "AXChildren", None)
            if error == 0 and value:
                return list(value)
        except Exception:
            pass
        return []

    def get_attribute(self, element: Any, attribute: str) -> Any:
        """Get a specific attribute from an accessibility element."""
        return self._get_attribute(element, attribute)

    def _get_attribute(self, element: Any, attribute: str) -> Any:
        """Get an attribute value from an accessibility element."""
        try:
            error, value = app_services.AXUIElementCopyAttributeValue(element, attribute, None)
            if error == 0:
                return value
        except Exception:
            pass
        return None

    def get_all_text(self, element: Any, max_depth: int = 15) -> str:
        """Recursively extract all text content from an element and its children.

        Args:
            element: The root accessibility element.
            max_depth: Maximum recursion depth to prevent infinite loops.

        Returns:
            All extracted text joined with newlines.
        """
        texts: list[str] = []
        self._collect_text(element, texts, depth=0, max_depth=max_depth)
        return "\n".join(texts)

    def _collect_text(
        self,
        element: Any,
        texts: list[str],
        depth: int,
        max_depth: int,
    ) -> None:
        """Recursively collect text from elements."""
        if depth > max_depth:
            return

        try:
            role = self._get_attribute(element, "AXRole")
            value = self._get_attribute(element, "AXValue")
            title = self._get_attribute(element, "AXTitle")
            description = self._get_attribute(element, "AXDescription")

            if role in ("AXStaticText", "AXTextField", "AXTextArea"):
                if value and str(value).strip():
                    texts.append(str(value).strip())
            elif title and str(title).strip():
                texts.append(str(title).strip())

            if description and str(description).strip():
                texts.append(str(description).strip())

            children = self._get_children(element)
            for child in children:
                self._collect_text(child, texts, depth + 1, max_depth)
        except Exception:
            pass

    def perform_action(self, element: Any, action: str = "AXPress") -> bool:
        """Perform an action on an accessibility element.

        Args:
            element: The target accessibility element.
            action: The action to perform (default: "AXPress").

        Returns:
            True if the action succeeded, False otherwise.
        """
        try:
            error = app_services.AXUIElementPerformAction(element, action)
            if error == 0:
                return True
            logger.debug("Action '%s' failed with error code: %d", action, error)
            return False
        except Exception:
            logger.exception("Exception performing action '%s'", action)
            return False

    def get_element_position(self, element: Any) -> tuple[float, float] | None:
        """Get the screen position (x, y) of an accessibility element.

        Returns:
            (x, y) tuple in screen coordinates, or None if unavailable.
        """
        try:
            error, value = app_services.AXUIElementCopyAttributeValue(
                element, "AXPosition", None
            )
            if error == 0 and value:
                return (value.x, value.y)
        except Exception:
            pass
        return None

    def get_element_size(self, element: Any) -> tuple[float, float] | None:
        """Get the size (width, height) of an accessibility element.

        Returns:
            (width, height) tuple, or None if unavailable.
        """
        try:
            error, value = app_services.AXUIElementCopyAttributeValue(
                element, "AXSize", None
            )
            if error == 0 and value:
                return (value.width, value.height)
        except Exception:
            pass
        return None

    def mouse_click_at(self, x: float, y: float) -> bool:
        """Perform a real mouse click at the given screen coordinates.

        Uses CGEvent to simulate a genuine mouse click that browsers
        will respond to, unlike AXPress which browsers often ignore.
        """
        try:
            import Quartz

            click_down = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventLeftMouseDown, (x, y), 0
            )
            click_up = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventLeftMouseUp, (x, y), 0
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, click_down)
            time.sleep(0.05)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, click_up)
            return True
        except Exception:
            logger.exception("Exception clicking at (%f, %f)", x, y)
            return False

    def mouse_click_on_element(self, element: Any) -> bool:
        """Click an element using a real mouse event at its on-screen center.

        Combines AXPosition + AXSize to find the center of the element,
        then uses CGEvent to post a real mouse click. Falls back to AXPress
        if position is unavailable.
        """
        pos = self.get_element_position(element)
        size = self.get_element_size(element)
        if pos and size:
            center_x = pos[0] + size[0] / 2
            center_y = pos[1] + size[1] / 2
            logger.info("Mouse-clicking at screen coords (%.0f, %.0f)", center_x, center_y)
            return self.mouse_click_at(center_x, center_y)
        logger.debug("Element position/size unavailable, falling back to AXPress")
        return self.perform_action(element, "AXPress")

    def click_element(self, element: Any) -> bool:
        """Click an element, preferring real mouse events over AXPress.

        Uses mouse_click_on_element which reads screen coordinates and
        posts a CGEvent — this works reliably in web browsers where
        AXPress is often ignored.
        """
        return self.mouse_click_on_element(element)

    def focus_element(self, element: Any) -> bool:
        """Bring focus to an element."""
        return self.perform_action(element, "AXRaise")

    def screenshot_window(self, window_element: Any | None = None) -> Any | None:
        """Capture the focused window as a CGImage for OCR processing.

        Returns:
            A CGImageRef that can be passed to Vision OCR, or None on failure.
        """
        try:
            import Quartz

            if window_element is None:
                window_element = self.get_focused_window()
            if window_element is None:
                return None

            pos = self.get_element_position(window_element)
            size = self.get_element_size(window_element)
            if not pos or not size:
                return None

            screen_rect = Quartz.CGRectMake(pos[0], pos[1], size[0], size[1])
            image = Quartz.CGWindowListCreateImage(
                screen_rect,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault,
            )
            return image
        except Exception:
            logger.exception("Exception capturing window screenshot")
            return None

    def find_text_on_screen(
        self,
        target_text: str,
        window_element: Any | None = None,
    ) -> list[tuple[float, float, str]]:
        """Find occurrences of target text on screen using Apple Vision OCR.

        Args:
            target_text: Text to search for (case-insensitive).
            window_element: The window to search. If None, uses focused window.

        Returns:
            List of (x, y, matched_text) tuples for each match found,
            sorted by confidence. Coordinates are the center of each match.
        """
        try:
            import Quartz
            import Vision

            cg_image = self.screenshot_window(window_element)
            if cg_image is None:
                return []

            window = self.get_focused_window() if window_element is None else window_element
            win_pos = self.get_element_position(window)
            if win_pos is None:
                win_pos = (0, 0)

            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                cg_image, None
            )
            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

            success, _ = handler.performRequests_error_([request], None)
            if not success:
                return []

            results: list[tuple[float, float, str]] = []
            observations = request.results() or []
            target_lower = target_text.lower()

            for obs in observations:
                candidates = obs.topCandidates_(1)
                if not candidates:
                    continue
                text = candidates[0].string()
                if target_lower in text.lower():
                    box = obs.boundingBox()
                    img_w = Quartz.CGImageGetWidth(cg_image)
                    img_h = Quartz.CGImageGetHeight(cg_image)
                    origin_x = box.origin.x * img_w
                    origin_y = (1 - box.origin.y - box.size.height) * img_h
                    center_x = win_pos[0] + origin_x + box.size.width * img_w / 2
                    center_y = win_pos[1] + origin_y + box.size.height * img_h / 2
                    results.append((center_x, center_y, text))

            return results
        except ImportError:
            logger.warning("Vision framework not available for OCR")
            return []
        except Exception:
            logger.exception("Exception in OCR text search")
            return []

    def set_value(self, element: Any, value: str) -> bool:
        """Set the value of a text field or similar element."""
        try:
            error = app_services.AXUIElementSetAttributeValue(element, "AXValue", value)
            if error == 0:
                return True
            logger.warning("Failed to set value, error code: %d", error)
            return False
        except Exception:
            logger.exception("Exception setting value")
            return False

    def type_text(self, text: str) -> None:
        """Type text using keyboard events (fallback for fields that don't support AXValue)."""
        try:
            for char in text:
                self._type_character(char)
        except Exception:
            logger.exception("Exception typing text")

    def _type_character(self, char: str) -> None:
        """Type a single character using CGEvents."""
        try:
            import Quartz

            event_down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(event_down, len(char), char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)

            event_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            Quartz.CGEventKeyboardSetUnicodeString(event_up, len(char), char)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)
        except Exception:
            logger.debug("Could not type character: %s", char)

    def action_names(self, element: Any) -> list[str]:
        """Get the list of actions supported by an element."""
        try:
            error, value = app_services.AXUIElementCopyActionNames(element, None)
            if error == 0 and value:
                return list(value)
        except Exception:
            pass
        return []

    def _scrollable_areas(self, element: Any, max_depth: int = 15) -> list[Any]:
        """Recursively find elements with AXScrollArea role (scroll views)."""
        results: list[Any] = []
        self._collect_scroll_areas(element, results, depth=0, max_depth=max_depth)
        return results

    def _collect_scroll_areas(
        self, element: Any, results: list[Any], depth: int, max_depth: int
    ) -> None:
        if depth > max_depth:
            return
        try:
            role = self._get_attribute(element, "AXRole")
            if role == "AXScrollArea":
                results.append(element)
            children = self._get_children(element)
            for child in children:
                self._collect_scroll_areas(child, results, depth + 1, max_depth)
        except Exception:
            pass

    def find_scrollable_element(self, element: Any, max_depth: int = 10) -> Any | None:
        """Recursively search for an element that supports AXScrollDown."""
        if max_depth <= 0:
            return None
        if "AXScrollDown" in self.action_names(element):
            return element
        children = self._get_children(element)
        for child in children:
            found = self.find_scrollable_element(child, max_depth - 1)
            if found is not None:
                return found
        return None

    def scroll_down(self, element: Any | None = None, clicks: int = 3) -> bool:
        """Scroll down within an element or the current window."""
        try:
            if element is None:
                element = self.get_focused_window()
            if element is None:
                return False

            scrollable = self.find_scrollable_element(element)
            if scrollable is not None:
                return self.perform_action(scrollable, "AXScrollDown")

            scroll_areas = self._scrollable_areas(element)
            for area in scroll_areas:
                if self.perform_action(area, "AXScrollDown"):
                    return True

            return self.perform_action(element, "AXScrollDown")
        except Exception:
            logger.exception("Exception scrolling down")
            return False

    def scroll_up(self, element: Any | None = None, clicks: int = 3) -> bool:
        """Scroll up within an element or the current window."""
        try:
            if element is None:
                element = self.get_focused_window()
            if element is None:
                return False

            scrollable = self.find_scrollable_element(element)
            if scrollable is not None:
                return self.perform_action(scrollable, "AXScrollUp")

            scroll_areas = self._scrollable_areas(element)
            for area in scroll_areas:
                if self.perform_action(area, "AXScrollUp"):
                    return True

            return self.perform_action(element, "AXScrollUp")
        except Exception:
            logger.exception("Exception scrolling up")
            return False
