"""
Memory Agent — context indexing and preference retrieval.
"""

from __future__ import annotations

import logging

from jarvis.core import memory

log = logging.getLogger("jarvis.memory_agent")


async def store_preference(key: str, value: str) -> str:
    memory.set_preference(key, value)
    return f"Noted: {key} = {value}"


async def recall_preference(key: str) -> str:
    val = memory.get_preference(key)
    if val:
        return f"Your preference for '{key}' is: {val}"
    return f"I don't have a preference stored for '{key}', sir."


async def store_note(content: str, title: str | None = None) -> str:
    nid = memory.add_note(content, title)
    return f"Note #{nid} saved, sir."


async def list_notes() -> str:
    notes = memory.list_notes(limit=10)
    if not notes:
        return "You have no saved notes, sir."
    items = []
    for n in notes:
        title_part = f" — {n['title']}" if n.get("title") else ""
        items.append(f"#{n['id']}{title_part}: {n['content'][:60]}")
    return "Notes: " + "; ".join(items)


async def get_context_summary() -> str:
    ctx = memory.summarise_context()
    return ctx or "No context available."
