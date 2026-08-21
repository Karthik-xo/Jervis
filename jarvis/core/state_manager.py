"""
Central State Manager for JARVIS AI OS.

Manages the single source of truth for the system-wide state machine:

    STANDBY → WAKE → LISTENING → THINKING → EXECUTING → SPEAKING → COOLDOWN → STANDBY

Also tracks:
  - Active mode (COMMAND / CONVERSATION)
  - Conversation session state and timeout
  - State transition history for debugging
  - Mic lock status for echo prevention

All state transitions are atomic, thread-safe, and broadcast via the
event bus so every subsystem stays synchronised.
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from enum import Enum
from typing import Any

from jarvis.core.event_bus import bus

log = logging.getLogger("jarvis.state_manager")


# ── State Enums ────────────────────────────────────────────────────────────

class JarvisState(str, Enum):
    STANDBY = "STANDBY"
    WAKE = "WAKE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    COOLDOWN = "COOLDOWN"
    ERROR = "ERROR"


class InteractionMode(str, Enum):
    COMMAND = "COMMAND"
    CONVERSATION = "CONVERSATION"


# ── Valid Transitions ──────────────────────────────────────────────────────

_VALID_TRANSITIONS: dict[JarvisState, set[JarvisState]] = {
    JarvisState.STANDBY:   {JarvisState.STANDBY, JarvisState.WAKE, JarvisState.LISTENING, JarvisState.THINKING, JarvisState.ERROR},
    JarvisState.WAKE:      {JarvisState.WAKE, JarvisState.LISTENING, JarvisState.STANDBY, JarvisState.ERROR},
    JarvisState.LISTENING:  {JarvisState.LISTENING, JarvisState.THINKING, JarvisState.STANDBY, JarvisState.ERROR},
    JarvisState.THINKING:   {JarvisState.THINKING, JarvisState.EXECUTING, JarvisState.SPEAKING, JarvisState.STANDBY, JarvisState.ERROR},
    JarvisState.EXECUTING:  {JarvisState.EXECUTING, JarvisState.SPEAKING, JarvisState.STANDBY, JarvisState.ERROR},
    JarvisState.SPEAKING:   {JarvisState.SPEAKING, JarvisState.COOLDOWN, JarvisState.LISTENING, JarvisState.STANDBY, JarvisState.ERROR},
    JarvisState.COOLDOWN:   {JarvisState.COOLDOWN, JarvisState.STANDBY, JarvisState.LISTENING, JarvisState.ERROR},
    JarvisState.ERROR:      {JarvisState.ERROR, JarvisState.STANDBY, JarvisState.COOLDOWN},
}


# ── State History Entry ────────────────────────────────────────────────────

_MAX_HISTORY = 50


class StateManager:
    """Singleton state manager for the entire JARVIS system.

    Thread-safe.  All state transitions are validated against the
    transition table and broadcast on the event bus.
    """

    def __init__(self) -> None:
        self._state = JarvisState.STANDBY
        self._mode = InteractionMode.COMMAND
        self._lock = threading.Lock()
        self._history: list[dict[str, Any]] = []
        self._mic_locked = False
        self._mic_lock_until: float = 0.0
        self._conversation_start: float = 0.0
        self._conversation_timeout: float = 120.0  # seconds
        self._last_activity: float = time.monotonic()

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def state(self) -> JarvisState:
        return self._state

    @property
    def mode(self) -> InteractionMode:
        return self._mode

    @property
    def is_busy(self) -> bool:
        """True if JARVIS is doing something (not idle)."""
        return self._state not in (JarvisState.STANDBY, JarvisState.ERROR)

    @property
    def is_mic_locked(self) -> bool:
        """True if mic should not accept input (speaking or cooldown)."""
        if self._mic_locked:
            return True
        if time.monotonic() < self._mic_lock_until:
            return True
        return self._state in (JarvisState.SPEAKING, JarvisState.COOLDOWN)

    @property
    def in_conversation(self) -> bool:
        return self._mode == InteractionMode.CONVERSATION

    @property
    def conversation_timed_out(self) -> bool:
        if not self.in_conversation:
            return False
        elapsed = time.monotonic() - self._last_activity
        return elapsed > self._conversation_timeout

    # ── State Transitions ──────────────────────────────────────────────

    async def transition(self, new_state: JarvisState) -> bool:
        """Transition to *new_state* with validation.

        Returns True on success, False if the transition is invalid.
        """
        with self._lock:
            old = self._state
            valid = _VALID_TRANSITIONS.get(old, set())
            if new_state not in valid:
                log.warning(
                    "Invalid state transition: %s → %s (allowed: %s)",
                    old.value, new_state.value,
                    ", ".join(s.value for s in valid),
                )
                return False

            self._state = new_state
            self._last_activity = time.monotonic()
            self._record(old, new_state)

        log.info("State: %s → %s", old.value, new_state.value)
        await bus.emit("voice:state_change", {
            "state": new_state.value,
            "previous": old.value,
            "mode": self._mode.value,
        })
        return True

    def transition_sync(self, new_state: JarvisState) -> bool:
        """Synchronous transition for use from threads."""
        with self._lock:
            old = self._state
            valid = _VALID_TRANSITIONS.get(old, set())
            if new_state not in valid:
                log.warning(
                    "Invalid state transition: %s → %s", old.value, new_state.value,
                )
                return False

            self._state = new_state
            self._last_activity = time.monotonic()
            self._record(old, new_state)

        log.info("State: %s → %s", old.value, new_state.value)
        bus.emit_sync("voice:state_change", {
            "state": new_state.value,
            "previous": old.value,
            "mode": self._mode.value,
        })
        return True

    def force_state(self, state: JarvisState) -> None:
        """Force state without validation (for error recovery only)."""
        with self._lock:
            old = self._state
            self._state = state
            self._record(old, state, forced=True)
        log.warning("State FORCED: %s → %s", old.value, state.value)

    # ── Mic Lock (Echo Prevention) ─────────────────────────────────────

    def lock_mic(self) -> None:
        """Lock the microphone (call before TTS)."""
        self._mic_locked = True

    def unlock_mic(self, cooldown_seconds: float = 3.0) -> None:
        """Unlock the mic with a cooldown period."""
        self._mic_locked = False
        self._mic_lock_until = time.monotonic() + cooldown_seconds

    # ── Conversation Mode ──────────────────────────────────────────────

    def start_conversation(self, timeout: float = 120.0) -> None:
        """Enter conversation mode."""
        self._mode = InteractionMode.CONVERSATION
        self._conversation_start = time.monotonic()
        self._conversation_timeout = timeout
        self._last_activity = time.monotonic()
        log.info("Entered CONVERSATION mode (timeout=%ds)", timeout)

    def end_conversation(self) -> None:
        """Return to command mode."""
        self._mode = InteractionMode.COMMAND
        self._conversation_start = 0.0
        log.info("Returned to COMMAND mode")

    def touch_activity(self) -> None:
        """Reset the conversation timeout timer."""
        self._last_activity = time.monotonic()

    # ── History ────────────────────────────────────────────────────────

    def _record(self, old: JarvisState, new: JarvisState, forced: bool = False) -> None:
        entry = {
            "from": old.value,
            "to": new.value,
            "timestamp": time.time(),
            "monotonic": time.monotonic(),
            "forced": forced,
        }
        self._history.append(entry)
        if len(self._history) > _MAX_HISTORY:
            self._history.pop(0)

    def get_history(self, limit: int = 20) -> list[dict]:
        return list(self._history[-limit:])

    # ── Debug ──────────────────────────────────────────────────────────

    def status_dict(self) -> dict[str, Any]:
        """Return a dict summary for API / dashboard use."""
        return {
            "state": self._state.value,
            "mode": self._mode.value,
            "mic_locked": self.is_mic_locked,
            "in_conversation": self.in_conversation,
            "last_activity": self._last_activity,
        }


# ── Module-level singleton ─────────────────────────────────────────────────

state_manager = StateManager()
