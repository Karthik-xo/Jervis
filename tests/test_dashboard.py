"""Tests for the dashboard module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestDashboardModule:
    def test_import(self):
        """Dashboard module should be importable."""
        from jarvis.ui import dashboard
        assert hasattr(dashboard, "create_app")
        assert hasattr(dashboard, "start_dashboard")
        assert hasattr(dashboard, "add_log_entry")

    def test_create_app(self):
        """App factory should produce an aiohttp Application."""
        from jarvis.ui.dashboard import create_app
        app = create_app()
        assert app is not None

    def test_log_buffer(self):
        """Log entries should be added to the buffer."""
        from jarvis.ui.dashboard import add_log_entry, _log_buffer
        initial_len = len(_log_buffer)
        add_log_entry("Test log message")
        assert len(_log_buffer) > initial_len
        assert _log_buffer[-1]["message"] == "Test log message"


class TestEventBus:
    def test_import(self):
        from jarvis.core.event_bus import bus, EventBus
        assert isinstance(bus, EventBus)

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self):
        from jarvis.core.event_bus import EventBus
        test_bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        test_bus.subscribe("test_event", handler)
        await test_bus.emit("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        from jarvis.core.event_bus import EventBus
        test_bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        test_bus.subscribe("test_event", handler)
        test_bus.unsubscribe("test_event", handler)
        await test_bus.emit("test_event", {"key": "value"})
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_listener_error_isolation(self):
        from jarvis.core.event_bus import EventBus
        test_bus = EventBus()
        received = []

        async def bad_handler(data):
            raise RuntimeError("Intentional error")

        async def good_handler(data):
            received.append(data)

        test_bus.subscribe("test_event", bad_handler)
        test_bus.subscribe("test_event", good_handler)
        await test_bus.emit("test_event", "test")
        # Good handler should still receive the event
        assert len(received) == 1

    def test_clear(self):
        from jarvis.core.event_bus import EventBus
        test_bus = EventBus()

        async def handler(data):
            pass

        test_bus.subscribe("a", handler)
        test_bus.subscribe("b", handler)
        test_bus.clear()
        assert len(test_bus._listeners) == 0
