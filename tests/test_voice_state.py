"""Tests for the Voice Agent state machine and echo prevention."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.agents.voice_agent import VoiceAgent, VoiceState
from jarvis.core.state_manager import state_manager


class TestVoiceStateTransitions:
    def test_initial_state(self):
        agent = VoiceAgent()
        assert agent.state == VoiceState.STANDBY

    def test_mic_not_locked_initially(self):
        state_manager.force_state(VoiceState.STANDBY)
        state_manager.unlock_mic(cooldown_seconds=0.0)
        assert not state_manager.is_mic_locked

    def test_speech_lock(self):
        state_manager.lock_mic()
        assert state_manager.is_mic_locked
        state_manager.unlock_mic(cooldown_seconds=1.0)
        # After unlock with cooldown, it should still be locked during the cooldown window
        assert state_manager.is_mic_locked

    def test_state_enum_values(self):
        assert VoiceState.STANDBY == "STANDBY"
        assert VoiceState.WAKE == "WAKE"
        assert VoiceState.LISTENING == "LISTENING"
        assert VoiceState.THINKING == "THINKING"
        assert VoiceState.EXECUTING == "EXECUTING"
        assert VoiceState.SPEAKING == "SPEAKING"
        assert VoiceState.COOLDOWN == "COOLDOWN"
        assert VoiceState.ERROR == "ERROR"

    def test_stop(self):
        agent = VoiceAgent()
        agent.stop()
        assert agent._stop_event.is_set()

    def test_sync_state_change(self):
        state_manager.force_state(VoiceState.STANDBY)
        state_manager.transition_sync(VoiceState.WAKE)
        assert state_manager.state == VoiceState.WAKE
        state_manager.transition_sync(VoiceState.LISTENING)
        assert state_manager.state == VoiceState.LISTENING
        state_manager.force_state(VoiceState.STANDBY)
        assert state_manager.state == VoiceState.STANDBY


class TestEchoPrevention:
    def test_lock_blocks_wake(self):
        """Mic should be locked during speech, preventing wake detection."""
        state_manager.lock_mic()
        assert state_manager.is_mic_locked

    def test_cooldown_after_speech(self):
        """After speech ends, there should be a cooldown period."""
        state_manager.lock_mic()
        state_manager.unlock_mic(cooldown_seconds=2.0)
        assert state_manager.is_mic_locked
