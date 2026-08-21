"""Tests for YouTube Agent and query extraction."""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.agents.youtube_agent import _clean_query


class TestYouTubeAgent:
    def test_clean_query_english(self):
        assert _clean_query("Jarvis play Anirudh songs on YouTube").lower() == "anirudh"
        assert _clean_query("play lofi beats").lower() == "lofi beats"
        assert _clean_query("search YouTube for Python tutorial").lower() == "python tutorial"

    def test_clean_query_tamil(self):
        cleaned = _clean_query("ஜார்விஸ் அனிருத் பாடல் இயக்கு")
        assert "அனிருத்" in cleaned
