"""
YouTube automation module for JARVIS AI OS.

Provides specialised functions for YouTube: searching, playing the top
result, extracting video info, and controlling playback (pause, resume, mute, unmute).
Uses Playwright for rich interaction or falls back to webbrowser.open for basic actions.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
import webbrowser

log = logging.getLogger("jarvis.youtube")


async def search_youtube(query: str) -> str:
    """Search YouTube for *query* and open results."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    try:
        from jarvis.automation.browser import new_page
        await new_page(url)
        log.info("YouTube search opened for: %s", query)
        return f"Searching YouTube for '{query}', sir."
    except Exception:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, webbrowser.open, url)
        return f"Searching YouTube for '{query}' in your browser, sir."


async def play_top_result(query: str) -> str:
    """Search YouTube and auto-play the first result."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    try:
        from jarvis.automation.browser import new_page, wait_for
        page = await new_page(url)
        await asyncio.sleep(2)
        try:
            first_video = await wait_for(page, "ytd-video-renderer a#video-title", timeout=8_000)
            if first_video:
                await first_video.click()
                return f"Playing top YouTube result for '{query}', sir."
        except Exception:
            pass
        return f"YouTube search opened for '{query}', sir."
    except Exception:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, webbrowser.open, url)
        return f"Searching YouTube for '{query}' in your browser, sir."


async def open_youtube() -> str:
    """Open YouTube homepage."""
    try:
        from jarvis.automation.browser import new_page
        await new_page("https://youtube.com")
        return "YouTube opened, sir."
    except Exception:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, webbrowser.open, "https://youtube.com")
        return "YouTube opened in your browser, sir."


async def pause_video() -> str:
    """Pause playback on the currently playing YouTube video."""
    try:
        from jarvis.automation.browser import get_active_page
        page = await get_active_page()
        # Toggle pause via video element or press 'k' / space
        paused = await page.evaluate(
            """() => {
                const video = document.querySelector('video');
                if (video && !video.paused) {
                    video.pause();
                    return true;
                }
                return false;
            }"""
        )
        if paused:
            return "Paused YouTube playback, sir."
        # Fallback press 'k'
        await page.keyboard.press("k")
        return "Paused YouTube playback, sir."
    except Exception as exc:
        log.warning("Pause YouTube video failed: %s", exc)
        return f"Could not pause video: {exc}"


async def resume_video() -> str:
    """Resume playback on the currently paused YouTube video."""
    try:
        from jarvis.automation.browser import get_active_page
        page = await get_active_page()
        resumed = await page.evaluate(
            """() => {
                const video = document.querySelector('video');
                if (video && video.paused) {
                    video.play();
                    return true;
                }
                return false;
            }"""
        )
        if resumed:
            return "Resumed YouTube playback, sir."
        await page.keyboard.press("k")
        return "Resumed YouTube playback, sir."
    except Exception as exc:
        log.warning("Resume YouTube video failed: %s", exc)
        return f"Could not resume video: {exc}"


async def toggle_playback() -> str:
    """Toggle play/pause on active video."""
    try:
        from jarvis.automation.browser import get_active_page
        page = await get_active_page()
        await page.keyboard.press("k")
        return "Toggled playback, sir."
    except Exception as exc:
        return f"Playback toggle failed: {exc}"


async def mute_video() -> str:
    """Mute YouTube video."""
    try:
        from jarvis.automation.browser import get_active_page
        page = await get_active_page()
        await page.keyboard.press("m")
        return "Muted YouTube video, sir."
    except Exception as exc:
        return f"Could not mute video: {exc}"


async def unmute_video() -> str:
    """Unmute YouTube video."""
    try:
        from jarvis.automation.browser import get_active_page
        page = await get_active_page()
        await page.keyboard.press("m")
        return "Unmuted YouTube video, sir."
    except Exception as exc:
        return f"Could not unmute video: {exc}"

