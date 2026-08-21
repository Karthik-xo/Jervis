"""
Terminal Status Panel — CLI HUD showing JARVIS state in the console.
"""

from __future__ import annotations

import logging
import time

import sys

log = logging.getLogger("jarvis.status_panel")


def _safe_print(text: str) -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    except Exception:
        # Fallback to ascii/latin-1 safe print
        clean = text.encode("ascii", errors="replace").decode("ascii")
        print(clean)


def print_banner() -> None:
    banner = r"""
    +----------------------------------------------------------+
    |         JARVIS AI OPERATING SYSTEM                       |
    |                                                          |
    |           AI Operating System v2.0 -- Phase 2            |
    |      Autonomous . Intelligent . Production-Grade         |
    +----------------------------------------------------------+
    """
    _safe_print(banner)


def print_status(state: str, port: int) -> None:
    _safe_print(f"\n  * Voice State: {state}")
    _safe_print(f"  * Dashboard:   http://127.0.0.1:{port}")
    _safe_print(f"  * Wake Trigger: Double Clap")
    _safe_print(f"  * Press Ctrl+C to stop\n")

