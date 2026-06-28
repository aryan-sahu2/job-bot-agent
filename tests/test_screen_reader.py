"""Tests for screen reader."""

from unittest.mock import MagicMock, patch

from src.screen.reader import ScreenReader


class TestScreenReader:
    def test_initialization(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            reader = ScreenReader()
            assert reader._system_wide is not None

    def test_get_attribute(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementCopyAttributeValue.return_value = (0, "test_value")

            reader = ScreenReader()
            element = MagicMock()
            result = reader.get_attribute(element, "AXTitle")
            assert result == "test_value"

    def test_get_attribute_failure(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementCopyAttributeValue.return_value = (1, None)

            reader = ScreenReader()
            element = MagicMock()
            result = reader.get_attribute(element, "AXTitle")
            assert result is None

    def test_get_children(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()

            child1 = MagicMock()
            child2 = MagicMock()
            mock_ax.AXUIElementCopyAttributeValue.return_value = (0, [child1, child2])

            reader = ScreenReader()
            element = MagicMock()
            children = reader.get_children(element)
            assert len(children) == 2
            assert children[0] == child1
            assert children[1] == child2

    def test_get_children_empty(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementCopyAttributeValue.return_value = (1, None)

            reader = ScreenReader()
            element = MagicMock()
            children = reader.get_children(element)
            assert len(children) == 0

    def test_perform_action_success(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementPerformAction.return_value = 0

            reader = ScreenReader()
            element = MagicMock()
            result = reader.perform_action(element, "AXPress")
            assert result is True

    def test_perform_action_failure(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementPerformAction.return_value = 1

            reader = ScreenReader()
            element = MagicMock()
            result = reader.perform_action(element, "AXPress")
            assert result is False

    def test_click_element(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementPerformAction.return_value = 0

            reader = ScreenReader()
            element = MagicMock()
            result = reader.click_element(element)
            assert result is True

    def test_focus_element(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementPerformAction.return_value = 0

            reader = ScreenReader()
            element = MagicMock()
            result = reader.focus_element(element)
            assert result is True

    def test_set_value_success(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementSetAttributeValue.return_value = 0

            reader = ScreenReader()
            element = MagicMock()
            result = reader.set_value(element, "test value")
            assert result is True

    def test_set_value_failure(self):
        with patch("src.screen.reader.app_services") as mock_ax:
            mock_ax.AXUIElementCreateSystemWide.return_value = MagicMock()
            mock_ax.AXUIElementSetAttributeValue.return_value = 1

            reader = ScreenReader()
            element = MagicMock()
            result = reader.set_value(element, "test value")
            assert result is False
