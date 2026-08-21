"""
Coding Agent for JARVIS AI OS.

Handles code generation, debugging, project analysis, refactoring,
and technical explanations for Python, JavaScript, React, APIs, and databases.
"""

from __future__ import annotations

import logging
from jarvis.services.llm_service import chat

log = logging.getLogger("jarvis.coding_agent")

_CODING_SYSTEM_PREF = (
    "You are JARVIS Coding Specialist. Assist the developer with clean, robust, "
    "and idiomatic code solutions, debugging tips, and architectural insights. "
    "Keep explanations concise and to the point."
)


async def handle_coding(text: str) -> str:
    """Handle coding-related requests."""
    log.info("Coding Agent processing: %s", text)
    prompt = f"[Developer Task]: {text}"
    return await chat(prompt)
