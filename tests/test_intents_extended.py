"""Tests for extended Commander Intent Classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.commander import classify, Intent


class TestExtendedIntents:
    def test_youtube_intent_english(self):
        intent, _ = classify("Jarvis play Anirudh songs")
        assert intent == Intent.YOUTUBE

        intent, _ = classify("Play lofi music on YouTube")
        assert intent == Intent.YOUTUBE

        intent, _ = classify("Open YouTube")
        assert intent == Intent.YOUTUBE or intent == Intent.SYSTEM

    def test_youtube_intent_tamil(self):
        intent, _ = classify("ஜார்விஸ் அனிருத் பாடல் இயக்கு")
        assert intent == Intent.YOUTUBE

        intent, _ = classify("யூடியூப் திற")
        assert intent == Intent.YOUTUBE or intent == Intent.SYSTEM

    def test_coding_intent(self):
        intent, _ = classify("Jarvis analyze my Python project")
        assert intent == Intent.CODING

        intent, _ = classify("Fix this JavaScript React error")
        assert intent == Intent.CODING

    def test_research_intent(self):
        intent, _ = classify("What is the latest AI news?")
        assert intent == Intent.RESEARCH

        intent, _ = classify("Search web for quantum computing advances")
        assert intent == Intent.RESEARCH

    def test_conversation_mode_intents(self):
        intent, meta = classify("Jarvis let's talk")
        assert intent == Intent.CONVERSATION
        assert meta["action"] == "start"

        intent, meta = classify("Stop conversation")
        assert intent == Intent.CONVERSATION
        assert meta["action"] == "stop"

    def test_system_intent(self):
        intent, _ = classify("Take a screenshot")
        assert intent == Intent.SYSTEM

        intent, _ = classify("Volume up")
        assert intent == Intent.SYSTEM

        intent, _ = classify("Lock computer")
        assert intent == Intent.SYSTEM

    def test_chat_intent_not_research(self):
        # Conversational questions should be CHAT, not RESEARCH
        intent, _ = classify("How are you?")
        assert intent == Intent.CHAT

        intent, _ = classify("Who are you?")
        assert intent == Intent.CHAT
