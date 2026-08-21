"""
System Agent for JARVIS AI OS.

Handles COMMAND and SYSTEM intents:
  - App launching / closing / focusing
  - Volume control (Up, Down, Mute)
  - Workstation Lock, Shutdown, Restart (with Security Agent confirmation)
  - System diagnostics & screenshots
"""

from __future__ import annotations

import logging
import re
from typing import Any

from jarvis.core.config import SITE_ALIASES, DESKTOP_APPS
from jarvis.services.permission_service import permission_manager, PermissionCategory
from jarvis.services.language_service import Language, detect_language

log = logging.getLogger("jarvis.system_agent")


async def handle_command(meta: dict[str, Any]) -> str:
    """Handle COMMAND-intent requests (open/close/focus apps and URLs)."""
    action = meta.get("action", "open")
    target = meta.get("target", "").lower().strip()
    raw = meta.get("raw", "")
    lang = detect_language(raw)

    # Strip filler prefixes
    for prefix in ("the ", "a ", "my ", "an "):
        if target.startswith(prefix):
            target = target[len(prefix):].strip()

    if action == "open":
        # Check UI Navigation Views
        ui_views = {
            "dashboard": "Dashboard",
            "settings": "Settings",
            "assistant": "AI Assistant",
            "ai assistant": "AI Assistant",
            "voice": "Voice Console",
            "voice console": "Voice Console",
            "agents": "AI Agents",
            "ai agents": "AI Agents",
            "agent network": "AI Agents",
            "memory": "Memory System",
            "memory system": "Memory System",
            "analytics": "Analytics",
            "automations": "Automations",
            "security": "Security",
            "command center": "Command Center",
            "knowledge base": "Knowledge Base",
            "documents": "Documents",
        }
        if target in ui_views:
            from jarvis.core.event_bus import bus
            await bus.emit("ui:navigate", {"tab": target})
            if lang == Language.TAMIL:
                return f"{ui_views[target]} பார்வைக்கு மாறுகிறேன் சார்."
            return f"Navigating to {ui_views[target]}, Sir."

        # YouTube check
        if target == "youtube" or "youtube" in target:
            from jarvis.agents.youtube_agent import handle_youtube
            return await handle_youtube(raw)

        # Check known site aliases
        if target in SITE_ALIASES:
            from jarvis.automation.desktop import open_url
            return await open_url(alias=target)

        # Check URL pattern
        url_match = re.match(r"(https?://\S+|\S+\.(?:com|org|net|io|ai|dev)\S*)", target, re.I)
        if url_match:
            from jarvis.automation.desktop import open_url
            return await open_url(url=url_match.group(1))

        # Check desktop app launch
        from jarvis.automation.desktop import launch_app
        return await launch_app(target)

    elif action == "close":
        from jarvis.automation.desktop import close_app
        return await close_app(target)

    elif action == "focus":
        from jarvis.automation.desktop import focus_app
        return await focus_app(target)

    if lang == Language.TAMIL:
        return f"மன்னிக்கவும் சார், '{action} {target}' கட்டளையை இயக்க முடியவில்லை."
    return f"I'm not sure how to handle '{action} {target}', Sir."


async def handle_system(meta: dict[str, Any]) -> str:
    """Handle SYSTEM-intent requests (screenshots, volume, lock, shutdown, restart, info)."""
    raw = meta.get("raw", "").lower()
    lang = detect_language(raw)

    # 1. Screenshot
    if any(w in raw for w in ["screenshot", "screen shot", "screen capture", "capture screen", "ஸ்கிரீன்ஷாட்"]):
        from jarvis.automation.system_control import take_screenshot
        return await take_screenshot()

    # 2. Volume controls
    if "volume up" in raw or "increase volume" in raw or "சத்தம் கூட்டு" in raw:
        from jarvis.automation.system_control import volume_up
        return await volume_up()

    if "volume down" in raw or "decrease volume" in raw or "சத்தம் குறை" in raw:
        from jarvis.automation.system_control import volume_down
        return await volume_down()

    if "mute" in raw or "அமைதி" in raw:
        from jarvis.automation.system_control import set_volume
        return await set_volume(action="mute")

    if "unmute" in raw:
        from jarvis.automation.system_control import set_volume
        return await set_volume(action="unmute")

    # 3. Lock Workstation
    if any(w in raw for w in ["lock pc", "lock computer", "lock screen", "lock workstation", "பூட்டு"]):
        from jarvis.automation.system_control import lock_workstation
        return await lock_workstation()

    # 4. Shutdown with Security Confirmation
    if any(w in raw for w in ["shutdown", "shut down", "turn off computer", "turn off pc"]):
        allowed, prompt = await permission_manager.request_action_permission(
            PermissionCategory.SYSTEM_SHUTDOWN,
            "shutting down the computer will close your current active session",
        )
        if not allowed:
            if lang == Language.TAMIL:
                return "சார், கணினியை அணைப்பது உங்கள் அமர்வை முடிக்கும். தொடரவா?"
            return prompt
        from jarvis.automation.system_control import execute_shutdown
        return await execute_shutdown()

    # 5. Restart with Security Confirmation
    if any(w in raw for w in ["restart", "reboot", "restart pc", "restart computer"]):
        allowed, prompt = await permission_manager.request_action_permission(
            PermissionCategory.SYSTEM_RESTART,
            "restarting the computer will reboot your system and close all open applications",
        )
        if not allowed:
            if lang == Language.TAMIL:
                return "சார், கணினியை மறுதொடக்கம் செய்யவா?"
            return prompt
        from jarvis.automation.system_control import execute_restart
        return await execute_restart()

    # 6. System diagnostics
    if any(w in raw for w in ["system info", "system status", "diagnostics", "நிலைமை"]):
        from jarvis.automation.system_control import get_system_info, get_resource_usage
        info = await get_system_info()
        resources = await get_resource_usage()
        return f"{info} {resources}"

    # 7. Time / Date
    if any(w in raw for w in ["what time", "current time", "what date", "what day", "நேரம்", "மணி"]):
        from jarvis.automation.system_control import get_system_info
        return await get_system_info()

    # 8. Battery
    if "battery" in raw or "பேட்டரி" in raw:
        from jarvis.automation.system_control import get_battery_status
        return await get_battery_status()

    # 9. CPU / Memory load
    if any(w in raw for w in ["cpu", "memory", "ram", "disk", "resource"]):
        from jarvis.automation.system_control import get_resource_usage
        return await get_resource_usage()

    # Fallback
    from jarvis.automation.system_control import get_system_info
    return await get_system_info()
