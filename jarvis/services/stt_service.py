"""
Async Speech-to-Text service using Faster-Whisper.

Provides non-blocking recording and transcription with gain normalisation,
RMS silence detection, VAD fallback, and bilingual English/Tamil support.
The Whisper model is lazy-loaded as a singleton.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import numpy as np
import sounddevice as sd

from jarvis.core.config import whisper_model_name, input_device, listen_seconds
from jarvis.services.language_service import Language, detect_language

log = logging.getLogger("jarvis.stt")

SAMPLE_RATE = 16_000  # Whisper requires 16 kHz mono


# ── Device resolution ───────────────────────────────────────────────────────

def _resolve_device(device: int | str | None = None) -> int | None:
    if isinstance(device, int):
        return device
    spec = (device or input_device() or "").strip()
    if not spec:
        return None
    if spec.isdigit():
        return int(spec)
    try:
        needle = spec.lower()
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] >= 1 and needle in dev["name"].lower():
                return idx
    except Exception as exc:
        log.warning("Could not resolve input device %r: %s", spec, exc)
    return None


# ── Model singleton ─────────────────────────────────────────────────────────

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        name = whisper_model_name()
        log.info("Loading Faster-Whisper model (%s)...", name)
        try:
            _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
        except Exception as exc:
            log.warning("int8 load failed (%s), falling back to float32.", exc)
            _MODEL = WhisperModel(name, device="cpu", compute_type="float32")
    return _MODEL


# ── Sync primitives (run in thread pool) ────────────────────────────────────

def _record_sync(seconds: float, device: int | str | None = None) -> np.ndarray:
    dev_idx = _resolve_device(device)
    log.info("Listening for %.1fs (device=%s)...", seconds, dev_idx or "default")
    try:
        audio = sd.rec(
            int(seconds * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=dev_idx,
        )
        sd.wait()
        return audio.flatten()
    except Exception as exc:
        log.error("Audio recording failed: %s", exc)
        return np.zeros(0, dtype=np.float32)


def _transcribe_sync(audio: np.ndarray, language: str | None = None) -> tuple[str, str]:
    """Transcribe audio array to (transcript, detected_language)."""
    if audio is None or audio.size == 0:
        return "", "en"

    peak = float(np.max(np.abs(audio)))
    if peak < 0.00005:
        log.info("Silent audio detected (peak=%.6f).", peak)
        return "", "en"

    # Normalise quiet audio
    if peak < 0.3:
        audio = (audio / (peak + 1e-6) * 0.85).astype(np.float32)

    model = _get_model()
    lang_param = None if language in (None, "auto", "auto-detect") else language

    # 1. Try with VAD filter
    try:
        segments, info = model.transcribe(audio, language=lang_param, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        detected = info.language if hasattr(info, "language") else "en"
    except Exception as exc:
        log.warning("VAD transcribe failed (%s), retrying without VAD.", exc)
        text = ""
        detected = "en"

    # 2. Fallback without VAD if nothing recognized
    if not text:
        try:
            segments, info = model.transcribe(audio, language=lang_param, vad_filter=False)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            detected = info.language if hasattr(info, "language") else "en"
        except Exception as exc:
            log.error("Transcription failed: %s", exc)
            return "", "en"

    if text:
        log.info("Transcribed: %r [lang=%s]", text, detected)
    return text, detected


# ── Async API ───────────────────────────────────────────────────────────────

async def record(seconds: float | None = None, device: int | str | None = None) -> np.ndarray:
    """Record audio asynchronously."""
    secs = seconds or listen_seconds()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _record_sync, secs, device)


async def transcribe(audio: np.ndarray, language: str | None = None) -> tuple[str, str]:
    """Transcribe audio array asynchronously. Returns (text, language)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _transcribe_sync, audio, language)


async def listen_and_transcribe(
    seconds: float | None = None,
    device: int | str | None = None,
    language: str | None = None,
) -> tuple[str, str]:
    """Record then transcribe — convenience wrapper returning (transcript, language)."""
    audio = await record(seconds, device)
    return await transcribe(audio, language=language)
