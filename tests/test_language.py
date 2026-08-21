"""Tests for Language Detection Service (English & Tamil)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.services.language_service import (
    Language,
    detect_language,
    get_response_language,
    normalize_for_intent,
    build_bilingual_response,
)


class TestLanguageDetection:
    def test_english_detection(self):
        assert detect_language("Jarvis open YouTube") == Language.ENGLISH
        assert detect_language("What is the current time?") == Language.ENGLISH
        assert detect_language("Take a screenshot") == Language.ENGLISH

    def test_tamil_detection(self):
        assert detect_language("ஜார்விஸ் யூடியூப் திற") == Language.TAMIL
        assert detect_language("அனிருத் பாடல் இயக்கு") == Language.TAMIL
        assert detect_language("வணக்கம் எப்படி இருக்கிறாய்") == Language.TAMIL

    def test_mixed_language_detection(self):
        # Mixed English and Tamil
        assert detect_language("Jarvis அனிருத் songs play") == Language.MIXED
        assert detect_language("YouTube திற") == Language.MIXED

    def test_empty_string_defaults_english(self):
        assert detect_language("") == Language.ENGLISH
        assert detect_language("   ") == Language.ENGLISH

    def test_get_response_language(self):
        assert get_response_language(Language.TAMIL) == "ta"
        assert get_response_language(Language.ENGLISH) == "en"
        assert get_response_language(Language.MIXED) == "en"

    def test_normalize_for_intent(self):
        normalized = normalize_for_intent("ஜார்விஸ் யூடியூப் திற")
        assert "youtube" in normalized.lower()
        assert "open" in normalized.lower()

    def test_bilingual_response_building(self):
        resp_en = build_bilingual_response("opening", "YouTube", Language.ENGLISH)
        assert "YouTube" in resp_en

        resp_ta = build_bilingual_response("opening", "யூடியூப்", Language.TAMIL)
        assert "யூடியூப்" in resp_ta
        assert "திறக்கப்படுகிறது" in resp_ta
