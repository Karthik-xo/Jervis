"""
Background reminder scheduler: polls the task DB for due-and-unspoken reminders
and speaks them via TTS. Runs in its own thread inside the main process.
"""

from __future__ import annotations

import logging
import threading
import time

import db
import tts

log = logging.getLogger("jarvis.scheduler")

POLL_INTERVAL_S = 5


def _speak_reminder(text: str) -> None:
    try:
        tts.speak(f"Reminder: {text}")
    except Exception as e:
        log.warning("Failed speaking reminder: %s", e)


def _poll_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            reminders = db.due_unnotified_reminders()
            for reminder in reminders:
                log.info("Reminder due: #%d - %s", reminder["id"], reminder["text"])
                db.mark_notified(reminder["id"])
                threading.Thread(
                    target=_speak_reminder, args=(reminder["text"],), daemon=True
                ).start()
        except Exception as e:
            log.warning("Scheduler polling error: %s", e)
        stop_event.wait(POLL_INTERVAL_S)


def start_reminder_thread() -> threading.Event:
    """Starts the background poller. Call `.set()` on the returned event to stop it."""
    stop_event = threading.Event()
    thread = threading.Thread(target=_poll_loop, args=(stop_event,), daemon=True)
    thread.start()
    log.info("Reminder scheduler started (polling every %ds).", POLL_INTERVAL_S)
    return stop_event
