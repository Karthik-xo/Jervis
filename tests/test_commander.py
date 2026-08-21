"""Tests for the Commander intent classifier."""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.commander import classify, Intent


class TestClassifyChat:
    def test_greeting_hello(self):
        intent, _ = classify("Hello")
        assert intent == Intent.CHAT

    def test_greeting_hi(self):
        intent, _ = classify("Hi there")
        assert intent == Intent.CHAT

    def test_how_are_you(self):
        intent, _ = classify("How are you?")
        assert intent == Intent.CHAT

    def test_joke(self):
        intent, _ = classify("Tell me a joke")
        assert intent == Intent.CHAT

    def test_who_are_you(self):
        intent, _ = classify("Who are you?")
        assert intent == Intent.CHAT

    def test_general_question(self):
        intent, _ = classify("What do you think about AI?")
        assert intent == Intent.CHAT

    def test_empty(self):
        intent, _ = classify("")
        assert intent == Intent.CHAT


class TestClassifyCommand:
    def test_open_youtube(self):
        intent, _ = classify("Open YouTube")
        assert intent in (Intent.YOUTUBE, Intent.SYSTEM, Intent.COMMAND)

    def test_launch_chrome(self):
        intent, meta = classify("Launch Chrome")
        assert intent in (Intent.SYSTEM, Intent.COMMAND)
        assert meta["action"] == "launch"

    def test_open_url(self):
        intent, _ = classify("Open https://example.com")
        assert intent in (Intent.BROWSER, Intent.SYSTEM, Intent.COMMAND)

    def test_close_app(self):
        intent, meta = classify("Close notepad")
        assert intent in (Intent.SYSTEM, Intent.COMMAND)
        assert meta["action"] == "close"

    def test_focus_app(self):
        intent, meta = classify("Focus Chrome")
        assert intent in (Intent.SYSTEM, Intent.COMMAND)
        assert meta["action"] == "focus"

    def test_go_to_github(self):
        intent, _ = classify("Go to GitHub")
        assert intent in (Intent.BROWSER, Intent.SYSTEM, Intent.COMMAND)


class TestClassifySearch:
    def test_search_keyword(self):
        intent, _ = classify("Search for quantum computing")
        assert intent in (Intent.SEARCH, Intent.RESEARCH)

    def test_google_keyword(self):
        intent, _ = classify("Google latest AI news")
        assert intent in (Intent.SEARCH, Intent.RESEARCH)

    def test_latest_news(self):
        intent, _ = classify("Latest AI news")
        assert intent in (Intent.SEARCH, Intent.RESEARCH)

    def test_look_up(self):
        intent, _ = classify("Look up astronomy facts")
        assert intent in (Intent.SEARCH, Intent.RESEARCH)


class TestClassifyTask:
    def test_remind_me(self):
        intent, _ = classify("Remind me to call John in 30 minutes")
        assert intent in (Intent.TASK, Intent.REMINDER)

    def test_add_task(self):
        intent, _ = classify("Add task buy groceries")
        assert intent == Intent.TASK

    def test_list_tasks(self):
        intent, _ = classify("List my tasks")
        assert intent == Intent.TASK

    def test_complete_task(self):
        intent, _ = classify("Complete task 5")
        assert intent == Intent.TASK

    def test_delete_task(self):
        intent, _ = classify("Delete task 3")
        assert intent == Intent.TASK


class TestClassifySystem:
    def test_screenshot(self):
        intent, _ = classify("Take a screenshot")
        assert intent == Intent.SYSTEM

    def test_system_info(self):
        intent, _ = classify("System status")
        assert intent == Intent.SYSTEM

    def test_time(self):
        intent, _ = classify("What time is it?")
        assert intent == Intent.SYSTEM

    def test_battery(self):
        intent, _ = classify("Battery level")
        assert intent == Intent.SYSTEM

    def test_cpu_usage(self):
        intent, _ = classify("CPU usage")
        assert intent == Intent.SYSTEM


class TestClassifyAutomation:
    def test_search_youtube_for(self):
        intent, _ = classify("Search YouTube for relaxing music")
        assert intent in (Intent.YOUTUBE, Intent.BROWSER, Intent.AUTOMATION)

    def test_open_and_search(self):
        intent, _ = classify("Open Gmail and search for invoices")
        assert intent in (Intent.BROWSER, Intent.AUTOMATION)

    def test_draft_email(self):
        intent, _ = classify("Open Gmail and draft an email")
        assert intent in (Intent.BROWSER, Intent.AUTOMATION)

    def test_play_on_youtube(self):
        intent, _ = classify("Play lofi beats on YouTube")
        assert intent in (Intent.YOUTUBE, Intent.BROWSER, Intent.AUTOMATION)


class TestUserVoiceCommands:
    def test_user_open_youtube(self):
        intent, _ = classify("Open YouTube")
        assert intent in (Intent.YOUTUBE, Intent.SYSTEM, Intent.COMMAND)

    def test_user_open_google(self):
        intent, meta = classify("Open Google")
        assert intent in (Intent.BROWSER, Intent.SYSTEM, Intent.COMMAND)

    def test_user_open_dashboard(self):
        intent, meta = classify("Open Dashboard")
        assert intent in (Intent.SYSTEM, Intent.COMMAND)

    def test_user_open_settings(self):
        intent, meta = classify("Open Settings")
        assert intent in (Intent.SYSTEM, Intent.COMMAND)

    def test_user_show_system_status(self):
        intent, _ = classify("Show System Status")
        assert intent == Intent.SYSTEM

    def test_user_create_task(self):
        intent, _ = classify("Create Task review code")
        assert intent == Intent.TASK
