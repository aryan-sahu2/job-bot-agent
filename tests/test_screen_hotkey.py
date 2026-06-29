"""Tests for global hotkey listener."""

import pytest

from src.screen.hotkey import GlobalHotkeyListener, _convert_hotkey_format


@pytest.fixture
def dummy_callback():
    async def callback():
        pass

    return callback


class TestConvertHotkeyFormat:
    def test_cmd_j(self):
        assert _convert_hotkey_format("cmd+j") == "<cmd>+j"

    def test_command_j(self):
        assert _convert_hotkey_format("command+j") == "<command>+j"

    def test_ctrl_shift_j(self):
        assert _convert_hotkey_format("ctrl+shift+j") == "<ctrl>+<shift>+j"

    def test_ctrl_space(self):
        assert _convert_hotkey_format("ctrl+space") == "<ctrl>+space"

    def test_alt_tab(self):
        assert _convert_hotkey_format("alt+tab") == "<alt>+tab"


class TestGlobalHotkeyListener:
    def test_initialization(self, dummy_callback):
        listener = GlobalHotkeyListener(callback=dummy_callback, hotkey_combo="cmd+j")
        assert listener._callback == dummy_callback
        assert listener._hotkey_combo == "cmd+j"
        assert listener._listener is None
        assert listener.is_running is False

    def test_is_running_property(self, dummy_callback):
        listener = GlobalHotkeyListener(callback=dummy_callback)
        assert listener.is_running is False
