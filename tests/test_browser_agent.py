"""Tests for upgraded Playwright Browser Agent, tab management, email workflow, and security."""

import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.automation import browser
from jarvis.agents.browser_agent import handle_automation, handle_email_workflow, handle_summarize_page
from jarvis.services.permission_service import permission_manager, PermissionCategory
from jarvis.core.commander import classify, Intent


@pytest.fixture(autouse=True)
def clean_permissions():
    """Ensure clean state before and after each test."""
    permission_manager._pending_confirmations.clear()
    yield
    permission_manager._pending_confirmations.clear()


class TestBrowserCapabilities:
    def test_browser_api_surface(self):
        """Ensure all required browser automation functions exist."""
        assert hasattr(browser, "new_page")
        assert hasattr(browser, "new_tab")
        assert hasattr(browser, "list_tabs")
        assert hasattr(browser, "switch_tab")
        assert hasattr(browser, "close_tab")
        assert hasattr(browser, "close_page")
        assert hasattr(browser, "navigate")
        assert hasattr(browser, "go_back")
        assert hasattr(browser, "go_forward")
        assert hasattr(browser, "reload_page")
        assert hasattr(browser, "click")
        assert hasattr(browser, "fill")
        assert hasattr(browser, "type_text")
        assert hasattr(browser, "press_key")
        assert hasattr(browser, "scroll")
        assert hasattr(browser, "fill_form")
        assert hasattr(browser, "get_text")
        assert hasattr(browser, "get_page_content")
        assert hasattr(browser, "extract_article_content")
        assert hasattr(browser, "screenshot")
        assert hasattr(browser, "handle_download")
        assert hasattr(browser, "search_google")
        assert hasattr(browser, "search_google_results")
        assert hasattr(browser, "search_in_page")
        assert hasattr(browser, "open_gmail_compose")
        assert hasattr(browser, "send_gmail_draft")

    def test_permission_categories_extended(self):
        """Ensure sensitive browser actions are registered in permission manager."""
        assert PermissionCategory.EMAIL_SEND.value == "EMAIL_SEND"
        assert PermissionCategory.FORM_SUBMISSION.value == "FORM_SUBMISSION"
        assert PermissionCategory.FILE_UPLOAD.value == "FILE_UPLOAD"
        assert PermissionCategory.ACCOUNT_SETTINGS.value == "ACCOUNT_SETTINGS"


class TestEmailWorkflow:
    @pytest.mark.asyncio
    async def test_email_missing_recipient(self):
        res = await handle_email_workflow("send an email saying hello")
        assert "recipient" in res.lower() or "யாருக்கு" in res

    @pytest.mark.asyncio
    async def test_email_requires_confirmation(self):
        with patch("jarvis.automation.browser.open_gmail_compose", new_callable=AsyncMock) as mock_compose:
            mock_compose.return_value = {
                "success": True,
                "page": None,
                "recipient": "john@example.com",
                "subject": "Status",
                "body": "All good",
                "message": "Drafted",
            }
            res = await handle_email_workflow("send an email to john@example.com with subject Status and body All good")
            # Permission manager must ask for confirmation
            assert "shall i send" in res.lower() or "continue" in res.lower() or "confirm" in res.lower() or permission_manager.has_pending_confirmation()


class TestBrowserAgentAutomation:
    @pytest.mark.asyncio
    async def test_tab_actions(self):
        with patch("jarvis.automation.browser.new_page", new_callable=AsyncMock) as mock_new:
            res = await handle_automation("open new tab")
            assert "new tab" in res.lower()
            mock_new.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_actions(self):
        with patch("jarvis.automation.browser.scroll", new_callable=AsyncMock) as mock_scroll:
            mock_scroll.return_value = "Scrolled down by 600px, sir."
            res = await handle_automation("scroll down")
            assert "scrolled" in res.lower()

    @pytest.mark.asyncio
    async def test_navigation_history(self):
        with patch("jarvis.automation.browser.go_back", new_callable=AsyncMock) as mock_back:
            mock_back.return_value = "Navigated back, sir."
            res = await handle_automation("go back")
            assert "back" in res.lower()

    @pytest.mark.asyncio
    async def test_screenshot_action(self):
        with patch("jarvis.automation.browser.screenshot", new_callable=AsyncMock) as mock_shot:
            mock_shot.return_value = "data/screenshots/screen_test.png"
            res = await handle_automation("take screenshot of page")
            assert "screenshot" in res.lower()
