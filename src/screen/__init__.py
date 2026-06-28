"""Screen-aware job application assistant.

This module provides a keyboard-activated, screen-aware job application
assistant that uses macOS Accessibility APIs to read and interact with
the user's current browser window.
"""

from src.screen.workflow import ScreenWorkflow

__all__ = ["ScreenWorkflow"]
