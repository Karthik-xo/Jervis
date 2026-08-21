"""Tests for Tanglish normalization, Web Research & Explanation workflow, and Intent Accuracy."""

import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.commander import classify, Intent
from jarvis.services.language_service import normalize_for_intent, detect_language, Language
from jarvis.agents.research_agent import _clean_research_query, perform_web_search


class TestTanglishAndIntentAccuracy:
    def test_tanglish_playwright_not_youtube(self):
        """
        Critical Requirement 7:
        'Jarvis, Google-la Playwright latest version search panni explain pannu.'
        Must be classified as RESEARCH / SEARCH, NOT YouTube!
        """
        intent, meta = classify("Jarvis, Google-la Playwright latest version search panni explain pannu.")
        assert intent in (Intent.RESEARCH, Intent.SEARCH)
        assert intent != Intent.YOUTUBE

    def test_search_and_explain_intent(self):
        """
        Critical Requirement 4:
        'Jarvis, search for the latest Python update and explain it to me.'
        Must be classified as RESEARCH.
        """
        intent, meta = classify("Jarvis, search for the latest Python update and explain it to me.")
        assert intent in (Intent.RESEARCH, Intent.SEARCH)

    def test_weather_queries(self):
        """Verify weather queries are classified as RESEARCH."""
        intent1, _ = classify("today weather")
        assert intent1 in (Intent.RESEARCH, Intent.SEARCH)

        intent2, _ = classify("today whether")
        assert intent2 in (Intent.RESEARCH, Intent.SEARCH)

    def test_youtube_commands_preserved(self):
        """Requirement 5: Existing YouTube automation is preserved."""
        intent, _ = classify("Search YouTube for relaxing music")
        assert intent == Intent.YOUTUBE

        intent2, _ = classify("Play Anirudh songs on YouTube")
        assert intent2 == Intent.YOUTUBE

        intent3, _ = classify("Open YouTube")
        assert intent3 in (Intent.YOUTUBE, Intent.SYSTEM)

    def test_clean_research_query(self):
        q1 = _clean_research_query("Jarvis, search for the latest Python update and explain it to me.")
        assert "latest Python update" in q1
        assert "explain it to me" not in q1

        q2 = _clean_research_query("Google-la Playwright latest version search panni explain pannu")
        assert "Playwright" in q2
