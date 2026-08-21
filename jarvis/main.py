"""
JARVIS AI OS v2.0 — Production-Grade Central Orchestrator.

Orchestrates startup of all subsystems:
  1. Configuration validation & environment loading
  2. Persistent Memory & State Manager initialization
  3. Background reminder scheduler
  4. Async WebSocket dashboard server & HUD
  5. Voice Agent (single session controller with anti-echo protection)
  6. Clap and wake-word detection loop

Entry point: ``python run.py`` or ``python -m jarvis.main``
"""

from __future__ import annotations

import asyncio
import logging
import sys
import webbrowser

from jarvis.core.config import load_env, validate_startup, web_port, auto_open_browser
from jarvis.core.event_bus import bus
from jarvis.core.state_manager import state_manager, JarvisState
from jarvis.core import memory
from jarvis.agents.voice_agent import VoiceAgent
from jarvis.ui.dashboard import start_dashboard, add_log_entry
from jarvis.ui.status_panel import print_banner, print_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("jarvis")


# ── Reminder Scheduler ─────────────────────────────────────────────────────

async def _reminder_loop(stop_event: asyncio.Event) -> None:
    """Poll for due reminders and speak them."""
    while not stop_event.is_set():
        try:
            reminders = memory.due_unnotified_reminders()
            for r in reminders:
                log.info("Reminder due: #%d — %s", r["id"], r["text"])
                memory.mark_notified(r["id"])
                add_log_entry(f"Reminder: {r['text']}")
                from jarvis.services.tts_service import speak_no_wait
                await speak_no_wait(f"Sir, here is your scheduled reminder: {r['text']}")
        except Exception as exc:
            log.warning("Scheduler error: %s", exc)
        await asyncio.sleep(5)


# ── Main Async Entry ───────────────────────────────────────────────────────

async def async_main() -> None:
    """Main async engine."""
    load_env()
    print_banner()
    report = validate_startup()

    # Start reminder scheduler
    reminder_stop = asyncio.Event()
    asyncio.create_task(_reminder_loop(reminder_stop))
    log.info("Reminder scheduler active.")

    # Create central Voice Agent
    voice_agent = VoiceAgent()

    # Start Dashboard & Holographic WebSocket server
    port = web_port()
    runner = None
    try:
        runner = await start_dashboard(voice_agent=voice_agent, port=port)
        log.info("Dashboard available at http://127.0.0.1:%d", port)
        if auto_open_browser():
            webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception as exc:
        log.warning("Could not start dashboard server: %s", exc)

    print_status(state_manager.state.value, port)
    log.info("JARVIS AI OS v2.0 active. Double-clap or speak to trigger.")
    add_log_entry("JARVIS AI OS v2.0 online. Central Commander and Agent Network initialized.")

    # Start Wake listener in background thread
    loop = asyncio.get_running_loop()
    voice_agent.start_listening(loop)

    # Keep alive loop
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("JARVIS shutdown requested by user.")
    finally:
        voice_agent.stop()
        reminder_stop.set()
        if runner:
            await runner.cleanup()
        try:
            from jarvis.automation.browser import close_browser
            await close_browser()
        except Exception:
            pass
        log.info("JARVIS OS shutdown complete.")


def main() -> int:
    """Synchronous entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
