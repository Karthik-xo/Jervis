#!/usr/bin/env python3
"""
JARVIS v2.5: double-clap to wake, voice/text command assistant with Web Dashboard HUD.

Flow: double clap -> record ~5s -> Whisper transcribe -> Claude/Brain -> execute -> speak reply.
Background threads poll for due reminders and serve the REST API & Web Dashboard HUD.
"""

from __future__ import annotations

import logging
import os
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv

import brain
import clap_detect
import scheduler
import server
import stt
import tts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("jarvis")


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
        log.info("Loaded environment from %s", env_path)
    else:
        log.warning("No .env found next to jarvis_assistant.py — relying on shell env vars.")


def on_wake() -> None:
    """Runs on a background thread every time a double clap is heard."""
    try:
        listen_seconds = float(os.environ.get("JARVIS_LISTEN_SECONDS", "5"))
        device_spec = os.environ.get("JARVIS_INPUT_DEVICE")
        server.add_log_entry("Double-clap wake detected! Listening for command...")
        
        transcript = stt.listen_and_transcribe(seconds=listen_seconds, device=device_spec)
        if not transcript:
            log.info("Heard nothing usable.")
            server.add_log_entry("No speech detected.")
            return

        server.add_log_entry(f"Heard: '{transcript}'")
        reply = brain.handle_command(transcript)
        log.info("Reply: %s", reply)
        server.add_log_entry(f"JARVIS Reply: '{reply}'")
        
        tts.speak(reply)
    except Exception:
        log.exception("Error handling voice command")


def main() -> int:
    _load_env()

    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not anthropic_key or anthropic_key.startswith("your_"):
        log.warning("ANTHROPIC_API_KEY is not set. JARVIS will run with local intent fallback.")

    # Start background reminder scheduler
    stop_reminders = scheduler.start_reminder_thread()

    # Start Web Dashboard API server
    web_port = int(os.environ.get("JARVIS_WEB_PORT", "8000"))
    try:
        server.start_server_thread(host="127.0.0.1", port=web_port)
        log.info("Web Dashboard available at http://127.0.0.1:%d", web_port)
        if os.environ.get("JARVIS_AUTO_OPEN_WEB", "true").lower() == "true":
            webbrowser.open(f"http://127.0.0.1:{web_port}")
    except Exception as e:
        log.warning("Could not start Web Dashboard server: %s", e)

    log.info("JARVIS Assistant System active. Double clap to trigger voice command.")

    try:
        clap_detect.listen_for_double_claps(on_wake)
    except KeyboardInterrupt:
        log.info("JARVIS system stopped by user.")
    finally:
        stop_reminders.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
