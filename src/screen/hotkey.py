"""Global hotkey listener for screen workflow activation."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from pynput import keyboard

logger = logging.getLogger(__name__)


def _convert_hotkey_format(hotkey_combo: str) -> str:
    """Convert user-friendly hotkey format to pynput format.

    Converts "cmd+j" to "<cmd>+j", "ctrl+shift+j" to "<ctrl>+<shift>+j", etc.
    """
    parts = [p.strip().lower() for p in hotkey_combo.split("+")]
    converted: list[str] = []

    modifier_names = {"cmd", "command", "ctrl", "control", "alt", "option", "shift"}

    for part in parts:
        if part in modifier_names:
            converted.append(f"<{part}>")
        else:
            converted.append(part)

    return "+".join(converted)


class GlobalHotkeyListener:
    """Listens for a global hotkey combination to trigger the screen workflow.

    Uses pynput for cross-platform global hotkey detection. On macOS,
    requires Accessibility permissions for the terminal/Python process.
    """

    def __init__(
        self,
        callback: Callable[[], Awaitable[None]],
        hotkey_combo: str = "cmd+j",
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize the hotkey listener.

        Args:
            callback: Async function to call when hotkey is pressed.
            hotkey_combo: Hotkey combination string (e.g., "cmd+j", "ctrl+shift+j").
            loop: The asyncio event loop to schedule callbacks on. If None,
                  uses the running loop at schedule time.
        """
        self._callback = callback
        self._hotkey_combo = hotkey_combo
        self._loop = loop
        self._listener: keyboard.GlobalHotKeys | None = None
        self._is_running = False

    def _on_activate(self) -> None:
        """Called when the hotkey combination is detected."""
        logger.info("Hotkey triggered: %s", self._hotkey_combo)
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(self._callback(), self._loop)

    def start(self) -> None:
        """Start listening for the global hotkey."""
        if self._is_running:
            logger.warning("Hotkey listener already running")
            return

        pynput_hotkey = _convert_hotkey_format(self._hotkey_combo)

        hotkey_map = {
            pynput_hotkey: self._on_activate,
        }

        logger.info(
            "Starting global hotkey listener: %s (pynput format: %s)",
            self._hotkey_combo,
            pynput_hotkey,
        )
        self._listener = keyboard.GlobalHotKeys(hotkey_map)
        self._is_running = True
        self._listener.start()

    def stop(self) -> None:
        """Stop listening for the global hotkey."""
        if self._listener and self._is_running:
            logger.info("Stopping global hotkey listener")
            self._listener.stop()
            self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check if the listener is currently active."""
        return self._is_running
