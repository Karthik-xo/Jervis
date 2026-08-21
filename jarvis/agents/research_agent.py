"""
Research Agent for JARVIS AI OS.

Performs live web search, aggregates snippets and page content,
strips HTML tags/entities, and synthesizes clean, concise answers using the AI Brain.
Never reads raw HTML or search markup aloud.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import urllib.parse
import urllib.request
from typing import Any

from jarvis.services.llm_service import chat
from jarvis.services.language_service import Language, detect_language

log = logging.getLogger("jarvis.research_agent")


def _clean_html(raw_html: str) -> str:
    """Strip all HTML tags, script blocks, and entities."""
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.DOTALL | re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_research_query(query: str) -> str:
    """Extract the clean search subject from conversational requests."""
    q = query.strip()
    # Strip leading punctuation/commas
    q = re.sub(r"^[,\.\?!;:\s]+", "", q)

    prefixes = [
        r"^(?:jarvis|ஜார்விஸ்)[,\s]*",
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+)[,\s]*",
        r"^(?:search\s+for|search|google|look\s+up|find|research)\s+",
        r"^(?:tell\s+me\s+about|what\s+is\s+the\s+latest\s+on|explain)\s+",
        r"^(?:on\s+google|in\s+google)\s+",
    ]
    for p in prefixes:
        q = re.sub(p, "", q, flags=re.I).strip()
        q = re.sub(r"^[,\.\?!;:\s]+", "", q)

    suffixes = [
        r"[,\s]+(?:and\s+)?(?:explain\s+it\s+to\s+me|explain\s+this|explain|solu|sollu|விளக்கு)[,\.\?!]*$",
        r"[,\s]+(?:on\s+google|in\s+google|google-la)[,\.\?!]*$",
    ]
    for p in suffixes:
        q = re.sub(p, "", q, flags=re.I).strip()

    # Final cleanup of trailing/leading punctuation
    q = re.sub(r"^[,\.\?!;:\s]+|[,\.\?!;:\s]+$", "", q).strip()
    return q or query.strip()


async def perform_web_search(query: str) -> str:
    """Execute search and return a clean, synthesized AI summary."""
    clean_q = _clean_research_query(query)
    loop = asyncio.get_running_loop()

    def _fetch_snippets() -> list[str]:
        try:
            url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(clean_q)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")

            raw_snippets = re.findall(
                r'<a class="result__snippet[^>]*>(.*?)</a>', raw_html, re.DOTALL
            )
            clean_list: list[str] = []
            seen = set()
            for s in raw_snippets[:6]:
                clean = _clean_html(s)
                if clean and clean not in seen and len(clean) > 20:
                    seen.add(clean)
                    clean_list.append(clean)
            return clean_list
        except Exception as exc:
            log.warning("DuckDuckGo search request failed: %s", exc)
            return []

    snippets = await loop.run_in_executor(None, _fetch_snippets)
    lang = detect_language(query)

    # If snippets empty, try Playwright Google search
    if not snippets:
        try:
            from jarvis.automation.browser import search_google
            content = await search_google(clean_q)
            if content and len(content) > 50:
                snippets = [content[:1000]]
        except Exception as p_exc:
            log.debug("Playwright search fallback bypassed: %s", p_exc)

    if not snippets:
        if lang == Language.TAMIL:
            return f"மன்னிக்கவும் சார், '{clean_q}' பற்றிய தகவல்களை உடனடியாக பெற முடியவில்லை."
        return f"I searched for '{clean_q}', but couldn't retrieve live results right now, Sir."

    joined_facts = "\n".join(f"- {s}" for s in snippets[:4])
    prompt = (
        f"You are JARVIS. Synthesize a concise, direct explanation for the user's research query: '{clean_q}'.\n"
        f"Research Information:\n{joined_facts}\n\n"
        "Instructions:\n"
        "1. Give a natural 1-3 sentence spoken summary.\n"
        "2. Do not recite raw search snippets, URLs, or HTML.\n"
        "3. If the user asked in Tamil, answer in clear Tamil; if English, answer in English."
    )
    summary = await chat(prompt)
    return summary


async def handle_search(query: str) -> str:
    """Entry point for RESEARCH / SEARCH intents."""
    return await perform_web_search(query)

