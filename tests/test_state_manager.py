"""Tests for State Manager and Atomic State Transitions."""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.core.state_manager import StateManager, JarvisState, InteractionMode


class TestStateManager:
    def test_initial_state(self):
        sm = StateManager()
        assert sm.state == JarvisState.STANDBY
        assert sm.mode == InteractionMode.COMMAND
        assert not sm.is_busy
        assert not sm.is_mic_locked

    @pytest.mark.asyncio
    async def test_valid_transitions(self):
        sm = StateManager()
        # STANDBY -> WAKE -> LISTENING -> THINKING -> EXECUTING -> SPEAKING -> COOLDOWN -> STANDBY
        assert await sm.transition(JarvisState.WAKE)
        assert sm.state == JarvisState.WAKE

        assert await sm.transition(JarvisState.LISTENING)
        assert sm.state == JarvisState.LISTENING

        assert await sm.transition(JarvisState.THINKING)
        assert sm.state == JarvisState.THINKING

        assert await sm.transition(JarvisState.EXECUTING)
        assert sm.state == JarvisState.EXECUTING

        assert await sm.transition(JarvisState.SPEAKING)
        assert sm.state == JarvisState.SPEAKING

        assert await sm.transition(JarvisState.COOLDOWN)
        assert sm.state == JarvisState.COOLDOWN

        assert await sm.transition(JarvisState.STANDBY)
        assert sm.state == JarvisState.STANDBY

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self):
        sm = StateManager()
        # Cannot jump directly from STANDBY to SPEAKING
        assert not await sm.transition(JarvisState.SPEAKING)
        assert sm.state == JarvisState.STANDBY

    def test_mic_locking_and_cooldown(self):
        sm = StateManager()
        assert not sm.is_mic_locked
        sm.lock_mic()
        assert sm.is_mic_locked
        sm.unlock_mic(cooldown_seconds=1.0)
        # Still locked during cooldown window
        assert sm.is_mic_locked

    def test_conversation_mode_tracking(self):
        sm = StateManager()
        assert not sm.in_conversation
        sm.start_conversation(timeout=50.0)
        assert sm.in_conversation
        assert not sm.conversation_timed_out
        sm.end_conversation()
        assert not sm.in_conversation
