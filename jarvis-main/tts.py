"""
Text-to-speech via ElevenLabs with local Windows SAPI5 / PowerShell fallback,
generalized from original welcome-line code with on-disk caching behavior.
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.tts")

CACHE_ENABLED = True


def _cache_dir() -> Path:
    override = (os.environ.get("JARVIS_WELCOME_CACHE_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent / ".cache" / "jarvis_tts"


def _elevenlabs_pcm_sample_rate(output_format: str) -> int:
    override = (os.environ.get("ELEVENLABS_PCM_SAMPLE_RATE") or "").strip()
    if override.isdigit():
        return int(override)
    if output_format.startswith("pcm_"):
        try:
            return int(output_format.split("_", maxsplit=1)[1])
        except (ValueError, IndexError):
            pass
    return 24000


def _env_config() -> tuple[str, str, str, int]:
    voice = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
    model = (os.environ.get("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2").strip()
    fmt = (os.environ.get("ELEVENLABS_OUTPUT_FORMAT") or "pcm_24000").strip()
    rate = _elevenlabs_pcm_sample_rate(fmt)
    return voice, model, fmt, rate


def _cache_path(text: str, voice_id: str, model_id: str, output_format: str) -> Path:
    key = f"{text}|{voice_id}|{model_id}|{output_format}".encode()
    digest = hashlib.sha256(key).hexdigest()[:24]
    return _cache_dir() / f"{digest}.wav"


def _play_pcm_wav_file(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as wf:
            ch, sw, rate = wf.getnchannels(), wf.getsampwidth(), wf.getframerate()
            if ch != 1 or sw != 2:
                return False
            raw = wf.readframes(wf.getnframes())
    except (OSError, wave.Error) as e:
        log.warning("Could not read cached audio: %s", e)
        return False
    if not raw:
        return False
    try:
        pcm_f = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(pcm_f, rate)
        sd.wait()
        return True
    except Exception as e:
        log.warning("Audio playback failed: %s", e)
        return False


def _save_pcm_wav_file(path: Path, pcm_bytes: bytes, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    tmp.replace(path)


def _speak_local_fallback(text: str) -> bool:
    """Use native Windows SAPI5 voice output as local fallback."""
    if sys.platform == "win32":
        try:
            # Escape single quotes for powershell string
            clean_text = text.replace("'", "''")
            ps_cmd = f"$v = New-Object -ComObject SAPI.SpVoice; $v.Speak('{clean_text}')"
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                check=False,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
            log.info("Spoke via Windows native SAPI5 TTS fallback.")
            return True
        except Exception as e:
            log.warning("Local SAPI5 TTS fallback failed: %s", e)
    return False


def speak(text: str) -> None:
    """Speak `text` out loud via ElevenLabs TTS, with automatic local Windows SAPI5 fallback."""
    text = text.strip()
    if not text:
        return

    vid, model_id, output_format, pcm_rate = _env_config()
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()

    if not vid or not api_key:
        log.info("ElevenLabs credentials missing; using local TTS fallback.")
        _speak_local_fallback(text)
        return

    cache_path = _cache_path(text, vid, model_id, output_format)
    if CACHE_ENABLED and cache_path.is_file():
        if _play_pcm_wav_file(cache_path):
            return

    try:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        chunks = client.text_to_speech.convert(
            voice_id=vid, text=text, model_id=model_id, output_format=output_format
        )
        raw = b"".join(chunks)
    except Exception as e:
        log.warning("ElevenLabs TTS failed (%s); switching to local TTS fallback.", e)
        _speak_local_fallback(text)
        return

    if not raw:
        _speak_local_fallback(text)
        return

    if CACHE_ENABLED:
        try:
            _save_pcm_wav_file(cache_path, raw, pcm_rate)
        except OSError as e:
            log.warning("Could not save TTS cache: %s", e)

    try:
        pcm_f = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(pcm_f, pcm_rate)
        sd.wait()
    except Exception as e:
        log.warning("Playing ElevenLabs audio failed (%s); trying local fallback.", e)
        _speak_local_fallback(text)
