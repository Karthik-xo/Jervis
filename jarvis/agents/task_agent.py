"""
Task Agent for JARVIS AI OS.

Handles task and reminder CRUD operations from English and Tamil voice/text commands.
"""

from __future__ import annotations

import logging
import re
from jarvis.core import memory
from jarvis.services.language_service import Language, detect_language

log = logging.getLogger("jarvis.task_agent")


async def handle_task(text: str) -> str:
    """Parse and execute task-related commands."""
    raw = text.strip()
    t = raw.lower()
    lang = detect_language(raw)

    # 1. Create task / reminder
    remind_match = re.search(
        r"(?:remind me to|add task|create task|new task|set reminder|add reminder|நினைவூட்டு|டாஸ்க்)\s+"
        r"(.+?)(?:\s+in\s+(\d+(?:\.\d+)?)\s+minutes?)?$",
        t, re.I,
    )
    if remind_match:
        task_text = remind_match.group(1).strip()
        due_mins = float(remind_match.group(2)) if remind_match.group(2) else None
        tid = memory.add_task(task_text, due_mins)
        if lang == Language.TAMIL:
            return f"டாஸ்க் #{tid} சேமிக்கப்பட்டது சார்: '{task_text}'"
        due_msg = f" (due in {due_mins}m)" if due_mins else ""
        return f"Saved task #{tid}: '{task_text}'{due_msg}"

    # 2. List tasks
    if any(q in t for q in ["list task", "my tasks", "show task", "what's on my task", "view task", "check task", "pending task", "டாஸ்க்குகள்"]):
        tasks = memory.list_tasks(include_done=False)
        if not tasks:
            if lang == Language.TAMIL:
                return "உங்களிடம் நிலுவையில் உள்ள பணிகள் எதுவும் இல்லை சார்."
            return "You have no pending tasks on your list, Sir."
        items = []
        for task in tasks:
            due = f" ({task['due_relative']})" if task.get("due_relative") else ""
            items.append(f"#{task['id']} {task['text']}{due}")
        if lang == Language.TAMIL:
            return "பணிகள்: " + "; ".join(items)
        return "Tasks: " + "; ".join(items)

    # 3. Complete task
    done_match = re.search(r"(?:complete|mark done|finish|done|முடிந்தது)\s+(?:task\s+)?#?(\d+)", t, re.I)
    if done_match:
        tid = int(done_match.group(1))
        ok = memory.complete_task(tid)
        if lang == Language.TAMIL:
            return f"டாஸ்க் #{tid} முடிவடைந்தது என குறிக்கப்பட்டது சார்." if ok else f"டாஸ்க் #{tid} கிடைக்கவில்லை."
        return f"Task #{tid} marked completed, Sir." if ok else f"No task #{tid} found."

    # 4. Delete task
    del_match = re.search(r"(?:delete|remove|நீக்கு)\s+(?:task\s+)?#?(\d+)", t, re.I)
    if del_match:
        tid = int(del_match.group(1))
        ok = memory.delete_task(tid)
        if lang == Language.TAMIL:
            return f"டாஸ்க் #{tid} நீக்கப்பட்டது சார்." if ok else f"டாஸ்க் #{tid} கிடைக்கவில்லை."
        return f"Task #{tid} deleted, Sir." if ok else f"No task #{tid} found."

    # 5. Clear completed
    if "clear completed" in t or "clear done" in t:
        count = memory.clear_completed_tasks()
        return f"Cleared {count} completed task(s), Sir."

    # Fallback add
    task_text = re.sub(r"^(add|create|new|set)\s+(task|reminder)\s*:?\s*", "", t, flags=re.I).strip()
    if task_text:
        tid = memory.add_task(task_text)
        return f"Saved task #{tid}: '{task_text}', Sir."

    return "I'm not sure what to do with that task request, Sir."
