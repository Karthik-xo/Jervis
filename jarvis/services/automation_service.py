"""
Automation service — bridge coordinating browser and desktop automation tasks.
"""

from __future__ import annotations

import logging

log = logging.getLogger("jarvis.automation_service")


async def execute_automation(description: str) -> str:
    """Parse a complex multi-step automation description and execute it.

    This is the central orchestrator for AUTOMATION-intent commands that
    require multiple sequential steps (e.g. 'open Gmail and draft an email').
    """
    from jarvis.services.llm_service import chat
    # For complex multi-step automation, we delegate to the LLM to break
    # the task into steps and execute them via tool calls
    return await chat(description)
