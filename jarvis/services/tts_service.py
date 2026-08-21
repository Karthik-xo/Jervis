"""
Async Text-to-Speech service for JARVIS AI OS.

Supports:
  - ElevenLabs Multilingual V2 (seamless English & Tamil Unicode pronunciation)
  - Windows SAPI5 Local fallback
  - Fast WAV caching to prevent redundant API calls
  - Barge-in support (instant audio cancellation on interruption)
  - Automatic microphone locking during speech to prevent feedback/echo loops
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import subprocess
import sys
import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd

from jarvis.core.config import (
    elevenlabs_api_key,
    elevenlabs_model_id,
    elevenlabs_output_format,
    elevenlabs_pcm_sample_rate,
    elevenlabs_voice_id,
    tts_cache_dir,
    voice_cooldown_seconds,
)
from jarvis.core.state_manager import state_manager, JarvisState

log = logging.getLogger("jarvis.tts")

_current_playback_stream = None
_playback_lock = threading.Lock()
_stop_playback_event = threading.Event()


def stop_playback() -> None:
    """Barge-in: Stop active TTS playback immediately."""
    _stop_playback_event.set()
    try:
        sd.stop()
        log.info("TTS playback stopped by barge-in/user interruption.")
    except Exception as exc:
        log.debug("Error stopping audio playback: %s", exc)


def _cache_key(text: str, vid: str, mid: str, fmt: str) -> Path:
    digest = hashlib.sha256(f"{text}|{vid}|{mid}|{fmt}".encode("utf-8")).hexdigest()[:24]
    return tts_cache_dir() / f"{digest}.wav"


def _play_wav(path: Path) -> bool:
    if _stop_playback_event.is_set():
        return False
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                return False
            raw = wf.readframes(wf.getnframes())
            rate = wf.getframerate()
    except Exception as exc:
        log.warning("Cannot read cached audio: %s", exc)
        return False

    if not raw or _stop_playback_event.is_set():
        return False

    try:
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(pcm, rate)
        sd.wait()
        return True
    except Exception as exc:
        log.warning("Audio playback failed: %s", exc)
        return False


def _save_wav(path: Path, pcm_bytes: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    tmp.replace(path)


def _estimate_duration(pcm_bytes: bytes, rate: int) -> float:
    num_samples = len(pcm_bytes) // 2
    return num_samples / rate if rate > 0 else 0.0


def _speak_sapi5(text: str) -> bool:
    """Local fallback voice on Windows."""
    if sys.platform != "win32" or _stop_playback_event.is_set():
        return False
    try:
        clean = text.replace("'", "''")
        ps_cmd = f"$v = New-Object -ComObject SAPI.SpVoice; $v.Speak('{clean}')"
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            check=False,
            creationflags=0x08000000,
        )
        return True
    except Exception as exc:
        log.warning("SAPI5 fallback failed: %s", exc)
        return False


def _speak_sync(text: str) -> float:
    """Speak text synchronously with echo prevention lock."""
    text = text.strip()
    if not text:
        return 0.0

    _stop_playback_event.clear()

    # Lock microphone input immediately
    state_manager.lock_mic()

    try:
        vid = elevenlabs_voice_id()
        api_key = elevenlabs_api_key()
        model_id = elevenlabs_model_id()
        fmt = elevenlabs_output_format()
        rate = elevenlabs_pcm_sample_rate()

        if not vid or not api_key:
            _speak_sapi5(text)
            return len(text.split()) / 2.5

        cache = _cache_key(text, vid, model_id, fmt)
        if cache.is_file():
            if _play_wav(cache):
                try:
                    with wave.open(str(cache), "rb") as wf:
                        return wf.getnframes() / wf.getframerate()
                except Exception:
                    return 2.0

        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=api_key)
            chunks = client.text_to_speech.convert(
                voice_id=vid,
                text=text,
                model_id=model_id,
                output_format=fmt,
            )
            raw = b"".join(chunks)
        except Exception as exc:
            log.warning("ElevenLabs TTS failed (%s); using fallback.", exc)
            _speak_sapi5(text)
            return len(text.split()) / 2.5

        if not raw or _stop_playback_event.is_set():
            _speak_sapi5(text)
            return len(text.split()) / 2.5

        duration = _estimate_duration(raw, rate)

        try:
            _save_wav(cache, raw, rate)
        except Exception as exc:
            log.warning("TTS cache save failed: %s", exc)

        try:
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(pcm, rate)
            sd.wait()
        except Exception as exc:
            log.warning("ElevenLabs playback failed: %s", exc)
            _speak_sapi5(text)

        return duration
    finally:
        # Unlock microphone with 3.0-second cooldown to completely prevent self-triggers
        cooldown = voice_cooldown_seconds()
        state_manager.unlock_mic(cooldown_seconds=cooldown)


async def speak(text: str) -> float:
    """Speak text asynchronously."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _speak_sync, text)


async def speak_no_wait(text: str) -> None:
    """Fire-and-forget speak helper with mic lock protection."""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _speak_sync, text)
