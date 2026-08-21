"""
YouTube Agent for JARVIS AI OS.

Handles all YouTube playback, search, artist selection, and music commands.
Integrates with the Playwright automation subsystem (and fallback browser launcher).
Supports English and Tamil commands.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from jarvis.services.language_service import Language, detect_language, build_bilingual_response
from jarvis.automation.youtube import search_youtube, play_top_result, open_youtube

log = logging.getLogger("jarvis.youtube_agent")


def _clean_query(raw: str) -> str:
    """Strip filler words to extract the clean search query."""
    q = raw.strip()
    # Strip common prefixes / suffixes
    strip_prefixes = [
        r"^(?:jarvis|ஜார்விஸ்)\s*",
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+)",
        r"^(?:search|look\s+up)\s+(?:on\s+youtube\s+for|in\s+youtube\s+for|youtube\s+for)\s+",
        r"^(?:search\s+for|search|find|look\s+up)\s+(?:on\s+youtube|in\s+youtube|youtube)\s+",
        r"^(?:play|search|find|open|look\s+up)\s+",
        r"^(?:on\s+youtube|in\s+youtube)\s+",
        r"^(?:songs?\s+of|songs?\s+by)\s+",
    ]
    for pat in strip_prefixes:
        q = re.sub(pat, "", q, flags=re.I).strip()

    strip_suffixes = [
        r"\s+(?:on\s+youtube|in\s+youtube)$",
        r"\s+(?:songs?|பாடல்கள்|பாடல்|videos?|மியூசிக்|music)$",
        r"\s+(?:play|இயக்கு|திற)$",
    ]
    for pat in strip_suffixes:
        q = re.sub(pat, "", q, flags=re.I).strip()

    return q or raw.strip()


async def handle_youtube(text: str, action: str = "auto") -> str:
    """Handle all YouTube-related intents."""
    raw = text.strip()
    lang = detect_language(raw)
    lower = raw.lower()

    # Just open YouTube
    if lower in ("open youtube", "youtube", "யூடியூப் திற", "யூடியூப்", "launch youtube"):
        res = await open_youtube()
        if lang == Language.TAMIL:
            return "சரி சார், யூடியூப் திறக்கப்படுகிறது."
        return "Sure Sir, opening YouTube."

    # Check for pause / resume controls
    if any(w in lower for w in ["pause youtube", "pause music", "pause video", "பாடலை நிறுத்து", "வீடியோவை நிறுத்து"]):
        from jarvis.automation.youtube import pause_video
        await pause_video()
        if lang == Language.TAMIL:
            return "சரி சார், யூடியூப் வீடியோ நிறுத்தப்பட்டது."
        return "Sure Sir, paused YouTube playback."

    if any(w in lower for w in ["resume youtube", "resume music", "resume video", "continue music", "பாடலை தொடர்"]):
        from jarvis.automation.youtube import resume_video
        await resume_video()
        if lang == Language.TAMIL:
            return "சரி சார், யூடியூப் வீடியோ தொடர்கிறது."
        return "Sure Sir, resumed YouTube playback."

    # Determine whether it's a 'play' or 'search' intent
    is_play = action == "play" or any(w in lower for w in [
        "play", "songs", "song", "music", "பாடல்", "பாடலை", "பாடல்கள்", "இயக்கு", "போடு"
    ])

    query = _clean_query(raw)
    if not query:
        query = "trending music"

    if is_play:
        log.info("YouTube Agent playing top result for: %s", query)
        await play_top_result(query)
        if lang == Language.TAMIL:
            return f"சரி சார், {query} பாடலை இயக்குகிறேன்."
        return f"Sure Sir, playing {query}."
    else:
        log.info("YouTube Agent searching: %s", query)
        await search_youtube(query)
        if lang == Language.TAMIL:
            return f"சரி சார், யூடியூபில் {query} தேடுகிறேன்."
        return f"Sure Sir, searching YouTube for {query}."

