"""
Language Detection Service for JARVIS AI OS.

Detects whether user input is English, Tamil, or mixed (English + Tamil),
and provides language-appropriate response templates.

Detection strategy:
  1. Unicode range analysis — Tamil characters are in U+0B80..U+0BFF
  2. Keyword heuristics for common Tamil/English triggers
  3. Mixed language support (e.g., "Jarvis அனிருத் songs play")
  4. Fallback to English if detection confidence is low

Supports:
  - Primary language: English
  - Secondary language: Tamil
  - Mixed (English + Tamil) commands
"""

from __future__ import annotations

import logging
import re
from enum import Enum

log = logging.getLogger("jarvis.language")


class Language(str, Enum):
    ENGLISH = "en"
    TAMIL = "ta"
    MIXED = "mixed"  # English + Tamil


# ── Tamil Unicode range ────────────────────────────────────────────────────

_TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
_ENGLISH_ALPHA = re.compile(r"[a-zA-Z]")

# Common Tamil keywords and their English equivalents
_TAMIL_KEYWORDS: dict[str, str] = {
    "திற": "open",
    "மூடு": "close",
    "தேடு": "search",
    "இயக்கு": "play",
    "நிறுத்து": "stop",
    "பாடல்": "song",
    "பாடலை": "song",
    "யூடியூப்": "youtube",
    "கூகுள்": "google",
    "சரி": "okay",
    "ஆம்": "yes",
    "இல்லை": "no",
    "உதவி": "help",
    "நேரம்": "time",
    "மணி": "time",
    "ஸ்கிரீன்ஷாட்": "screenshot",
    "டாஸ்க்": "task",
    "நினைவூட்டு": "remind",
    "வணக்கம்": "hello",
    "ஹலோ": "hello",
    "ஜார்விஸ்": "jarvis",
    "பேசலாம்": "let's talk",
    "பேச்சு நிறுத்து": "stop talking",
    "ஸ்டாண்ட்பை": "standby",
}

# Tamil response templates
_TAMIL_RESPONSES: dict[str, str] = {
    "acknowledge": "சரி சார்,",
    "opening": "திறக்கப்படுகிறது",
    "playing": "இயக்குகிறேன்",
    "searching": "தேடுகிறேன்",
    "done": "முடிந்தது சார்",
    "error": "மன்னிக்கவும் சார், பிழை ஏற்பட்டது",
    "greeting": "வணக்கம் சார், எப்படி உதவ முடியும்?",
    "standby": "நிற்கிறேன் சார்",
    "confirm": "இதை செய்யட்டுமா சார்?",
    "listening": "கேட்கிறேன் சார்",
    "not_understood": "மன்னிக்கவும், புரியவில்லை சார்",
}

# English response templates
_ENGLISH_RESPONSES: dict[str, str] = {
    "acknowledge": "Sure, sir.",
    "opening": "Opening",
    "playing": "Playing",
    "searching": "Searching",
    "done": "Done, sir.",
    "error": "I'm sorry sir, an error occurred",
    "greeting": "Hello, sir. How can I help?",
    "standby": "Standing by, sir.",
    "confirm": "Shall I proceed, sir?",
    "listening": "I'm listening, sir.",
    "not_understood": "I didn't catch that, sir.",
}


# ── Detection ──────────────────────────────────────────────────────────────

def detect_language(text: str) -> Language:
    """Detect the language of *text*.

    Returns Language.TAMIL if predominantly Tamil characters,
    Language.ENGLISH if predominantly English, or Language.MIXED
    if both are significantly present.
    """
    if not text or not text.strip():
        return Language.ENGLISH  # Default fallback

    tamil_chars = len(_TAMIL_RANGE.findall(text))
    english_chars = len(_ENGLISH_ALPHA.findall(text))
    total = tamil_chars + english_chars

    if total == 0:
        return Language.ENGLISH  # No alphabetic chars — fallback

    tamil_ratio = tamil_chars / total
    english_ratio = english_chars / total

    # Predominantly Tamil
    if tamil_ratio > 0.6:
        return Language.TAMIL

    # Predominantly English
    if english_ratio > 0.8:
        return Language.ENGLISH

    # Mixed content — both languages present
    if tamil_chars > 0 and english_chars > 0:
        return Language.MIXED

    return Language.ENGLISH


def get_response_language(detected: Language) -> str:
    """Get the ISO 639-1 language code for response generation.

    For MIXED input, responds in English (primary language).
    """
    if detected == Language.TAMIL:
        return "ta"
    return "en"


def get_response_template(key: str, language: Language) -> str:
    """Get a response template in the appropriate language."""
    if language == Language.TAMIL:
        return _TAMIL_RESPONSES.get(key, _ENGLISH_RESPONSES.get(key, ""))
    return _ENGLISH_RESPONSES.get(key, "")


def get_whisper_language_hint(detected: Language) -> str | None:
    """Get the Whisper language code for STT.

    Returns None for auto-detection (recommended for mixed input).
    """
    if detected == Language.TAMIL:
        return "ta"
    if detected == Language.ENGLISH:
        return "en"
    return None  # Auto-detect for mixed


# ── Tamil keyword extraction ──────────────────────────────────────────────

def extract_tamil_intent_keywords(text: str) -> dict[str, str]:
    """Extract known Tamil keywords and return their English equivalents.

    Useful for intent detection on mixed-language input.
    """
    found: dict[str, str] = {}
    text_lower = text.strip()
    for tamil_word, english_equiv in _TAMIL_KEYWORDS.items():
        if tamil_word in text_lower:
            found[tamil_word] = english_equiv
    return found


_TANGLISH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bgoogle[-_]?la\b", re.I), "on google"),
    (re.compile(r"\byoutube[-_]?la\b", re.I), "on youtube"),
    (re.compile(r"\bbrowser[-_]?la\b", re.I), "in browser"),
    (re.compile(r"\bsearch\s+(?:panni|pannu)\b", re.I), "search"),
    (re.compile(r"\bexplain\s+pannu\b", re.I), "explain"),
    (re.compile(r"\bopen\s+pannu\b", re.I), "open"),
    (re.compile(r"\bplay\s+pannu\b", re.I), "play"),
    (re.compile(r"\b(?:anuppu|anupu|send\s+pannu)\b", re.I), "send"),
    (re.compile(r"\b(?:sollu|solu)\b", re.I), "tell"),
    (re.compile(r"\b(?:paaru|paarkalam)\b", re.I), "look"),
    (re.compile(r"\beduthu\b", re.I), "take"),
    (re.compile(r"\bclose\s+pannu\b", re.I), "close"),
    (re.compile(r"\bscroll\s+pannu\b", re.I), "scroll"),
    (re.compile(r"\b(?:summarize\s+pannu|summary\s+pannu)\b", re.I), "summarize"),
    (re.compile(r"\btoday\s+whether\b", re.I), "today weather"),
]


def normalize_for_intent(text: str) -> str:
    """Replace known Tamil keywords and Tanglish slang with English equivalents for intent detection.

    This allows the commander to classify Tamil and mixed-language input
    using the existing English pattern tables.

    Example:
        "ஜார்விஸ் யூடியூப் திற" → "jarvis youtube open"
        "Google-la Playwright latest version search panni explain pannu" → "on google Playwright latest version search explain"
    """
    result = text.strip()
    # 1. Replace Tamil unicode keywords
    for tamil_word, english_equiv in _TAMIL_KEYWORDS.items():
        result = result.replace(tamil_word, english_equiv)
    # 2. Replace Tanglish patterns
    for pat, repl in _TANGLISH_PATTERNS:
        result = pat.sub(repl, result)
    # Clean up extra whitespace
    result = re.sub(r"\s+", " ", result).strip()
    return result


def build_bilingual_response(
    action: str,
    target: str,
    language: Language,
) -> str:
    """Build a natural response in the detected language.

    Examples:
        build_bilingual_response("opening", "YouTube", Language.ENGLISH)
        → "Sure sir, opening YouTube."

        build_bilingual_response("opening", "YouTube", Language.TAMIL)
        → "சரி சார், யூடியூப் திறக்கப்படுகிறது."
    """
    if language == Language.TAMIL:
        ack = _TAMIL_RESPONSES.get("acknowledge", "சரி சார்,")
        verb = _TAMIL_RESPONSES.get(action, action)
        return f"{ack} {target} {verb}."

    # English or Mixed
    ack = _ENGLISH_RESPONSES.get("acknowledge", "Sure, sir.")
    verb = _ENGLISH_RESPONSES.get(action, action)
    return f"{ack} {verb} {target}."
