"""Tests for browser automation module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestBrowserModule:
    def test_import(self):
        """Browser module should be importable."""
        from jarvis.automation import browser
        assert hasattr(browser, "new_page")
        assert hasattr(browser, "navigate")
        assert hasattr(browser, "click")
        assert hasattr(browser, "fill")
        assert hasattr(browser, "get_text")
        assert hasattr(browser, "close_browser")
        assert hasattr(browser, "search_google")


class TestYouTubeModule:
    def test_import(self):
        """YouTube module should be importable."""
        from jarvis.automation import youtube
        assert hasattr(youtube, "search_youtube")
        assert hasattr(youtube, "play_top_result")
        assert hasattr(youtube, "open_youtube")


class TestDesktopModule:
    def test_import(self):
        """Desktop module should be importable."""
        from jarvis.automation import desktop
        assert hasattr(desktop, "launch_app")
        assert hasattr(desktop, "open_url")
        assert hasattr(desktop, "focus_app")
        assert hasattr(desktop, "close_app")
        assert hasattr(desktop, "open_path")


class TestSystemControlModule:
    def test_import(self):
        """System control module should be importable."""
        from jarvis.automation import system_control
        assert hasattr(system_control, "take_screenshot")
        assert hasattr(system_control, "get_system_info")
        assert hasattr(system_control, "get_battery_status")
        assert hasattr(system_control, "get_resource_usage")
