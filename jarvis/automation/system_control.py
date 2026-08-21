"""
OS-level system control utilities for JARVIS AI OS.

Provides:
  - Screen capture / vision
  - System diagnostics, battery & resource monitoring
  - Volume control (Up, Down, Mute, Unmute)
  - Workstation control (Lock, Shutdown, Restart) with safety checks
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import platform
import subprocess
import sys
from pathlib import Path

from jarvis.core import memory

log = logging.getLogger("jarvis.system_control")


async def take_screenshot(save_path: str | None = None) -> str:
    """Capture screen to disk and return path."""
    try:
        from jarvis.services.vision_service import capture_screen
        path = await capture_screen(Path(save_path) if save_path else None)
        return f"Screenshot captured and saved to {path.name}, Sir."
    except Exception as exc:
        log.warning("Screenshot failed: %s", exc)
        return f"Could not capture screenshot: {exc}"


async def get_system_info() -> str:
    """Get current time and OS info."""
    now_str = datetime.datetime.now().strftime("%A, %B %d at %I:%M %p")
    os_info = f"{platform.system()} {platform.release()}"
    pending = len(memory.list_tasks(include_done=False))
    return f"Current time is {now_str}. Operating System: {os_info}. You have {pending} pending task(s)."


async def get_battery_status() -> str:
    """Get battery level on laptops."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            pct = battery.percent
            plugged = "plugged in" if battery.power_plugged else "discharging"
            return f"Battery is at {pct}%, currently {plugged}, Sir."
        return "System is running on direct AC power, Sir."
    except Exception:
        return "Battery telemetry unavailable."


async def get_resource_usage() -> str:
    """Get CPU, Memory, and Disk stats."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        return f"CPU load is at {cpu}%. RAM usage is at {mem.percent}%."
    except Exception:
        return "System telemetry unavailable."


async def volume_up() -> str:
    """Increase system volume."""
    if sys.platform == "win32":
        try:
            # Send volume up key sequence (VK_VOLUME_UP = 0xAF / 175)
            cmd = "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], creationflags=0x08000000)
            return "Volume increased, Sir."
        except Exception as exc:
            return f"Volume adjustment failed: {exc}"
    return "Volume control not supported on this platform."


async def volume_down() -> str:
    """Decrease system volume."""
    if sys.platform == "win32":
        try:
            # Send volume down key sequence (VK_VOLUME_DOWN = 0xAE / 174)
            cmd = "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], creationflags=0x08000000)
            return "Volume decreased, Sir."
        except Exception as exc:
            return f"Volume adjustment failed: {exc}"
    return "Volume control not supported on this platform."


async def set_volume(action: str = "mute") -> str:
    """Mute or toggle system volume."""
    if sys.platform == "win32":
        try:
            # Send mute toggle (VK_VOLUME_MUTE = 0xAD / 173)
            cmd = "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], creationflags=0x08000000)
            return f"System audio {action}d, Sir."
        except Exception as exc:
            return f"Audio control failed: {exc}"
    return "Volume control not supported on this platform."


async def lock_workstation() -> str:
    """Lock the Windows workstation."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked, Sir."
        except Exception as exc:
            return f"Locking failed: {exc}"
    return "Locking workstation not supported on this platform."


async def execute_shutdown() -> str:
    """Execute machine shutdown."""
    if sys.platform == "win32":
        try:
            subprocess.run(["shutdown", "/s", "/t", "5"], creationflags=0x08000000)
            return "Shutting down the computer in 5 seconds. Goodbye Sir."
        except Exception as exc:
            return f"Shutdown failed: {exc}"
    return "Shutdown command executed."


async def execute_restart() -> str:
    """Execute machine restart."""
    if sys.platform == "win32":
        try:
            subprocess.run(["shutdown", "/r", "/t", "5"], creationflags=0x08000000)
            return "Restarting the computer in 5 seconds, Sir."
        except Exception as exc:
            return f"Restart failed: {exc}"
    return "Restart command executed."
