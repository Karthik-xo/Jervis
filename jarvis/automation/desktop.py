"""
Desktop application control module.

Launch, focus, switch, and close applications on Windows.
Supports: Chrome, VS Code, Cursor, Antigravity, WhatsApp, Telegram,
File Explorer, Notepad, Terminal, and custom executables.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import webbrowser

from jarvis.core.config import DESKTOP_APPS, SITE_ALIASES

log = logging.getLogger("jarvis.desktop")


# ── App launching ───────────────────────────────────────────────────────────

def _launch_app_sync(app_name: str) -> str:
    app_lower = (app_name or "").lower().strip()
    
    # Strip common leading article/filler words
    for prefix in ("the ", "a ", "my ", "an "):
        if app_lower.startswith(prefix):
            app_lower = app_lower[len(prefix):].strip()

    if not app_lower:
        return "Please specify an application or site to open, sir."

    # Check if target is a known site alias
    if app_lower in SITE_ALIASES:
        return _open_url_sync(None, app_lower)

    target = DESKTOP_APPS.get(app_lower, app_lower)

    # Check if executable exists on system PATH or is explicit file/protocol
    is_protocol = ":" in target or target.endswith(".exe")
    executable_path = shutil.which(target) or shutil.which(app_lower)
    is_valid_target = executable_path is not None or is_protocol or os.path.exists(target) or app_lower in DESKTOP_APPS

    if not is_valid_target:
        log.warning("Unrecognized application launch request: '%s'", app_name)
        return f"I could not find an application named '{app_name}' on your system, sir."

    if sys.platform == "win32":
        try:
            os.startfile(target)
            log.info("Successfully launched %s via os.startfile", app_name)
            return f"Launched {app_name}, sir."
        except OSError as exc:
            log.warning("os.startfile failed for '%s': %s", target, exc)
            if executable_path:
                try:
                    subprocess.Popen([executable_path], creationflags=subprocess.CREATE_NO_WINDOW)
                    return f"Launched {app_name}, sir."
                except Exception as ex:
                    log.warning("Subprocess launch failed for '%s': %s", executable_path, ex)

            web_fallbacks = {
                "spotify": "https://open.spotify.com",
                "whatsapp": "https://web.whatsapp.com",
                "telegram": "https://web.telegram.org",
            }
            if app_lower in web_fallbacks:
                webbrowser.open(web_fallbacks[app_lower])
                return f"Opened {app_name} web version in your browser, sir."
            return f"Could not launch {app_name}, sir."
    else:
        try:
            cmd_target = executable_path or app_lower
            subprocess.Popen([cmd_target])
            return f"Launched {app_name}, sir."
        except Exception as exc:
            return f"Could not launch {app_name}: {exc}"


async def launch_app(app_name: str) -> str:
    """Launch an application by name (async wrapper)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _launch_app_sync, app_name)


# ── URL opening ─────────────────────────────────────────────────────────────

def _open_url_sync(url: str | None, alias: str | None) -> str:
    alias_lower = (alias or "").lower().strip()
    resolved = url or SITE_ALIASES.get(alias_lower)
    if not resolved and alias_lower:
        resolved = f"https://{alias_lower}.com"
    if not resolved:
        return f"No URL found for '{alias}'."
    if not resolved.startswith(("http://", "https://")):
        resolved = "https://" + resolved
    webbrowser.open(resolved)
    return f"Opened {alias or resolved}, sir."


async def open_url(url: str | None = None, alias: str | None = None) -> str:
    """Open a URL or site alias in the default browser."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _open_url_sync, url, alias)


# ── Window management (Windows) ────────────────────────────────────────────

def _focus_window_sync(app_name: str) -> str:
    """Attempt to focus a running application's window."""
    if sys.platform != "win32":
        return f"Window focusing not supported on {sys.platform}."

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        target_lower = app_name.lower().strip()
        exe_map = {
            "chrome": "chrome.exe",
            "cursor": "cursor.exe",
            "vscode": "code.exe",
            "vs code": "code.exe",
            "notepad": "notepad.exe",
            "explorer": "explorer.exe",
            "terminal": "windowsterminal.exe",
        }
        target_exe = exe_map.get(target_lower, f"{target_lower}.exe").lower()

        found_hwnd = None

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lp):
            nonlocal found_hwnd
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == 0:
                return True
            hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not hproc:
                return True
            try:
                buf = ctypes.create_unicode_buffer(4096)
                sz = wintypes.DWORD(len(buf))
                if kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
                    if os.path.basename(buf.value).lower() == target_exe:
                        found_hwnd = int(hwnd)
                        return False  # Stop enumeration
            finally:
                kernel32.CloseHandle(hproc)
            return True

        user32.EnumWindows(_enum, 0)
        if found_hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(found_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(found_hwnd)
            return f"Focused {app_name}, sir."
        return f"{app_name} does not appear to be running, sir."
    except Exception as exc:
        return f"Could not focus {app_name}: {exc}"


async def focus_app(app_name: str) -> str:
    """Focus a running application's window."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _focus_window_sync, app_name)


def _close_app_sync(app_name: str) -> str:
    """Close an application by process name."""
    if sys.platform == "win32":
        exe_map = {
            "chrome": "chrome.exe",
            "cursor": "cursor.exe",
            "vscode": "code.exe",
            "notepad": "notepad.exe",
        }
        target = exe_map.get(app_name.lower().strip(), f"{app_name.lower().strip()}.exe")
        try:
            subprocess.run(
                ["taskkill", "/IM", target, "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return f"Closed {app_name}, sir."
        except Exception as exc:
            return f"Could not close {app_name}: {exc}"
    else:
        try:
            subprocess.run(["pkill", "-f", app_name.lower()], capture_output=True)
            return f"Closed {app_name}, sir."
        except Exception as exc:
            return f"Could not close {app_name}: {exc}"


async def close_app(app_name: str) -> str:
    """Close an application."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _close_app_sync, app_name)


# ── File / folder launching ────────────────────────────────────────────────

async def open_path(path: str) -> str:
    """Open a file or folder with the default handler."""
    def _open():
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return f"Opened {path}, sir."

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _open)
    except Exception as exc:
        return f"Could not open {path}: {exc}"
