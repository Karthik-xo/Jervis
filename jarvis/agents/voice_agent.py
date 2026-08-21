"""
Voice Agent for JARVIS AI OS.

Single Voice Session Controller managing:
  - Atomic State Machine (powered by core/state_manager.py)
  - Silent Standby Mode
  - Anti-Echo & Anti-Self-Trigger protection
  - Double-Clap and Wake-Word detection
  - Single Command Mode vs Continuous Real-Time Conversation Mode
  - Barge-in / Interruptible TTS
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

import numpy as np
import sounddevice as sd

from jarvis.core.config import (
    input_device,
    listen_seconds,
    voice_cooldown_seconds,
    conversation_timeout_seconds,
    wake_word,
)
from jarvis.core.event_bus import bus
from jarvis.core.state_manager import state_manager, JarvisState, InteractionMode

VoiceState = JarvisState


log = logging.getLogger("jarvis.voice_agent")

_SAMPLE_RATE = 44100
_BLOCK_MS = 40
_CHANNELS = 1
_SPIKE_RATIO = 7.0
_COOLDOWN_S = 0.45
_MIN_GAP = 0.05
_MAX_GAP = 0.35
_RETRIGGER_RATIO = 0.55
_NOISE_ALPHA = 0.992
_MIN_RMS = 0.012
_QUIET_GATE = 2.2


def _rms(block: np.ndarray) -> float:
    b = block.astype(np.float64)
    if b.ndim > 1:
        b = np.mean(b, axis=1)
    return float(np.sqrt(np.mean(b ** 2))) if b.size else 0.0


def _resolve_device() -> int | None:
    spec = (input_device() or "").strip()
    if not spec:
        return None
    if spec.isdigit():
        return int(spec)
    needle = spec.lower()
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] >= 1 and needle in dev["name"].lower():
            return idx
    return None


class VoiceAgent:
    """Central Voice Session Controller."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session_lock = asyncio.Lock()

    @property
    def state(self) -> JarvisState:
        return state_manager.state

    @property
    def mode(self) -> InteractionMode:
        return state_manager.mode

    # ── Wake and Listening Loop ────────────────────────────────────────────

    def start_listening(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start background wake listening in a dedicated daemon thread."""
        self._loop = loop
        thread = threading.Thread(target=self._wake_listener_loop, daemon=True)
        thread.start()
        log.info("Voice Agent wake listener started.")

    def _wake_listener_loop(self) -> None:
        """Continuously listen for double clap or wake events while in STANDBY."""
        device_idx = _resolve_device()
        blocksize = max(int(_SAMPLE_RATE * _BLOCK_MS / 1000), 1)
        noise_floor = 1e-4
        last_double = 0.0
        first_clap: float | None = None
        armed = True

        log.info("Clap & Wake listener active on device: %s", device_idx or "default")

        try:
            with sd.InputStream(
                device=device_idx,
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype="float32",
                blocksize=blocksize,
            ) as stream:
                while not self._stop_event.is_set():
                    # If microphone is locked (speaking or cooldown), skip reading
                    if state_manager.is_mic_locked:
                        time.sleep(0.05)
                        continue

                    # If not in STANDBY and not in CONVERSATION, wait
                    if state_manager.state not in (JarvisState.STANDBY,):
                        time.sleep(0.05)
                        continue

                    data, _ = stream.read(blocksize)
                    level = _rms(data)

                    quiet_gate = noise_floor * _QUIET_GATE
                    if level < quiet_gate:
                        noise_floor = _NOISE_ALPHA * noise_floor + (1 - _NOISE_ALPHA) * level
                        noise_floor = max(noise_floor, 1e-7)

                    threshold = max(noise_floor * _SPIKE_RATIO, _MIN_RMS)
                    now = time.monotonic()
                    retrigger = threshold * _RETRIGGER_RATIO

                    if level < retrigger:
                        armed = True

                    if armed and level >= threshold and (now - last_double) >= _COOLDOWN_S:
                        armed = False
                        if first_clap is None:
                            first_clap = now
                        else:
                            gap = now - first_clap
                            if _MIN_GAP <= gap <= _MAX_GAP:
                                first_clap = None
                                last_double = now
                                log.info("Double-clap trigger detected (gap=%.3fs).", gap)
                                if self._loop and not self._loop.is_closed():
                                    asyncio.run_coroutine_threadsafe(
                                        self.trigger_voice_session(trigger_source="double_clap"),
                                        self._loop,
                                    )
                            else:
                                first_clap = now

        except Exception as exc:
            log.error("Wake listener error: %s", exc)
            state_manager.force_state(JarvisState.ERROR)

    # ── Voice Session Cycle ────────────────────────────────────────────────

    async def trigger_voice_session(self, trigger_source: str = "wake") -> None:
        """Trigger an end-to-end voice interaction cycle."""
        if state_manager.is_mic_locked:
            log.debug("Wake ignored: mic is currently locked.")
            return

        if state_manager.state not in (JarvisState.STANDBY,):
            log.debug("Wake ignored: system not in STANDBY (state=%s).", state_manager.state.value)
            return

        async with self._session_lock:
            await self._run_voice_pipeline()

    async def _run_voice_pipeline(self) -> None:
        """Execute single command flow or enter conversation session."""
        try:
            # 1. WAKE
            await state_manager.transition(JarvisState.WAKE)
            await bus.emit("log:new", {"message": "Wake detected. Listening..."})

            # 2. LISTEN
            await state_manager.transition(JarvisState.LISTENING)
            from jarvis.services.stt_service import listen_and_transcribe
            transcript, detected_lang = await listen_and_transcribe()

            if not transcript:
                log.info("No speech detected.")
                await bus.emit("log:new", {"message": "No speech detected. Returning to standby."})
                await state_manager.transition(JarvisState.STANDBY)
                return

            await bus.emit("log:new", {"message": f"Heard [{detected_lang}]: '{transcript}'"})
            await bus.emit("voice:transcript", {"text": transcript, "language": detected_lang})

            # 3. THINKING
            await state_manager.transition(JarvisState.THINKING)

            # 4. EXECUTING
            await state_manager.transition(JarvisState.EXECUTING)
            from jarvis.core.commander import dispatch
            reply = await dispatch(transcript)

            log.info("Reply: %s", reply)
            await bus.emit("log:new", {"message": f"JARVIS: '{reply}'"})

            # 5. SPEAKING (with automatic microphone lock)
            await state_manager.transition(JarvisState.SPEAKING)
            from jarvis.services.tts_service import speak
            await speak(reply)

            # 6. COOLDOWN (3-second echo cooldown)
            await state_manager.transition(JarvisState.COOLDOWN)
            cooldown = voice_cooldown_seconds()
            await asyncio.sleep(cooldown)

            # 7. Check if in active conversation mode
            if state_manager.in_conversation and not state_manager.conversation_timed_out:
                log.info("Conversation mode active: listening for next user utterance...")
                # Loop back to listening directly without needing wake-word
                asyncio.create_task(self._run_conversation_turn())
            else:
                if state_manager.in_conversation:
                    state_manager.end_conversation()
                await state_manager.transition(JarvisState.STANDBY)

        except Exception as exc:
            log.exception("Voice pipeline error: %s", exc)
            await state_manager.transition(JarvisState.ERROR)
            await asyncio.sleep(2.0)
            state_manager.force_state(JarvisState.STANDBY)

    async def _run_conversation_turn(self) -> None:
        """Handle a subsequent turn in active conversation mode."""
        if not state_manager.in_conversation or state_manager.conversation_timed_out:
            state_manager.end_conversation()
            await state_manager.transition(JarvisState.STANDBY)
            return

        try:
            await state_manager.transition(JarvisState.LISTENING)
            from jarvis.services.stt_service import listen_and_transcribe
            # Listen with conversational timeout
            transcript, detected_lang = await listen_and_transcribe(seconds=4.5)

            if not transcript:
                log.info("Conversation turn silent.")
                state_manager.end_conversation()
                await state_manager.transition(JarvisState.STANDBY)
                return

            state_manager.touch_activity()
            await bus.emit("log:new", {"message": f"Conversation [{detected_lang}]: '{transcript}'"})

            # Check for conversation exit commands
            lower = transcript.lower()
            if any(w in lower for w in ["stop conversation", "go to standby", "stop talking", "bye", "நிறுத்து"]):
                state_manager.end_conversation()
                await state_manager.transition(JarvisState.SPEAKING)
                from jarvis.services.tts_service import speak
                await speak("Standing by, Sir.")
                await state_manager.transition(JarvisState.COOLDOWN)
                await asyncio.sleep(voice_cooldown_seconds())
                await state_manager.transition(JarvisState.STANDBY)
                return

            await state_manager.transition(JarvisState.THINKING)
            await state_manager.transition(JarvisState.EXECUTING)
            from jarvis.core.commander import dispatch
            reply = await dispatch(transcript)

            await state_manager.transition(JarvisState.SPEAKING)
            from jarvis.services.tts_service import speak
            await speak(reply)

            await state_manager.transition(JarvisState.COOLDOWN)
            await asyncio.sleep(voice_cooldown_seconds())

            if state_manager.in_conversation and not state_manager.conversation_timed_out:
                asyncio.create_task(self._run_conversation_turn())
            else:
                state_manager.end_conversation()
                await state_manager.transition(JarvisState.STANDBY)

        except Exception as exc:
            log.exception("Conversation turn error: %s", exc)
            state_manager.end_conversation()
            await state_manager.transition(JarvisState.STANDBY)

    # ── Text Command (from dashboard UI) ───────────────────────────────────

    async def handle_text_command(self, text: str) -> str:
        """Process manual text command from the Web Dashboard."""
        await state_manager.transition(JarvisState.THINKING)
        await bus.emit("log:new", {"message": f"Dashboard Command: '{text}'"})

        try:
            await state_manager.transition(JarvisState.EXECUTING)
            from jarvis.core.commander import dispatch
            reply = await dispatch(text)

            await bus.emit("log:new", {"message": f"JARVIS: '{reply}'"})

            # Speak output in background
            asyncio.create_task(self._speak_text_reply(reply))
            return reply
        except Exception as exc:
            log.exception("Text command error")
            state_manager.force_state(JarvisState.STANDBY)
            return f"Error executing command: {exc}"

    async def _speak_text_reply(self, text: str) -> None:
        try:
            if state_manager.state != JarvisState.STANDBY:
                await state_manager.transition(JarvisState.SPEAKING)
            from jarvis.services.tts_service import speak
            await speak(text)
            if state_manager.state == JarvisState.SPEAKING:
                await state_manager.transition(JarvisState.COOLDOWN)
                await asyncio.sleep(voice_cooldown_seconds())
        except Exception as exc:
            log.warning("Speak text reply error: %s", exc)
        finally:
            if state_manager.state != JarvisState.STANDBY:
                await state_manager.transition(JarvisState.STANDBY)

    def stop(self) -> None:
        self._stop_event.set()
