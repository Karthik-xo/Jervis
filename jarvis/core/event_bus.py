"""
Async publish-subscribe Event Bus for decoupled inter-agent communication.

Every agent, service, and UI component publishes and subscribes to typed
events on a shared singleton bus.  This eliminates direct coupling between
modules and enables real-time dashboard updates, voice state broadcasting,
and coordinated multi-agent workflows.

Usage
-----
    from jarvis.core.event_bus import bus

    async def on_voice_state(data):
        print(data)

    bus.subscribe("voice:state_change", on_voice_state)
    await bus.emit("voice:state_change", {"state": "LISTENING"})
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

log = logging.getLogger("jarvis.event_bus")

Callback = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """Lightweight async event emitter with topic-based subscriptions."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callback]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, event: str, callback: Callback) -> None:
        """Register *callback* to be called whenever *event* is emitted."""
        self._listeners[event].append(callback)
        log.debug("Subscribed %s to '%s'", callback.__qualname__, event)

    def unsubscribe(self, event: str, callback: Callback) -> None:
        """Remove a previously registered callback."""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            pass

    async def emit(self, event: str, data: Any = None) -> None:
        """Emit *event* with optional *data* to all registered listeners.

        Listener exceptions are logged but never propagate to the emitter.
        """
        listeners = list(self._listeners.get(event, []))
        if not listeners:
            return
        for cb in listeners:
            try:
                await cb(data)
            except Exception:
                log.exception("Listener %s failed on event '%s'", cb.__qualname__, event)

    def emit_sync(self, event: str, data: Any = None) -> None:
        """Fire-and-forget emit from synchronous code.

        Schedules the async emit onto the running loop (or creates a task
        if already inside one).  Safe to call from threads via
        ``loop.call_soon_threadsafe``.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event, data))
        except RuntimeError:
            # No running loop — run synchronously (startup / tests)
            asyncio.run(self.emit(event, data))

    def clear(self) -> None:
        """Remove all subscriptions (useful for testing)."""
        self._listeners.clear()


# Module-level singleton
bus = EventBus()
