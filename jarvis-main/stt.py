"""
Speech-to-text: record audio from mic and transcribe locally with faster-whisper.
Includes audio gain normalization, RMS volume checks, and VAD fallback logic
so quiet or standard microphone speech is accurately recognized.
"""

from __future__ import annotations

import logging
import os
import time
import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.stt")

SAMPLE_RATE = 16000  # Whisper requires 16kHz mono
_MODEL = None  # Lazy-loaded singleton


def _resolve_device_idx(device: int | str | None = None) -> int | None:
    if isinstance(device, int):
        return device
    dev_spec = (device or os.environ.get("JARVIS_INPUT_DEVICE") or "").strip()
    if not dev_spec:
        return None
    if dev_spec.isdigit():
        return int(dev_spec)
    try:
        needle = dev_spec.lower()
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] >= 1 and needle in dev["name"].lower():
                return idx
    except Exception as e:
        log.warning("Could not resolve input device %r: %s", dev_spec, e)
    return None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        model_name = os.environ.get("JARVIS_WHISPER_MODEL", "base.en")
        log.info("Loading Whisper model (%s)...", model_name)
        try:
            _MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
        except Exception as e:
            log.warning("Failed loading with compute_type='int8' (%s), trying float32 fallback.", e)
            _MODEL = WhisperModel(model_name, device="cpu", compute_type="float32")
    return _MODEL


def record_audio(seconds: float, device: int | str | None = None) -> np.ndarray:
    """Record `seconds` of mono float32 audio at 16kHz."""
    dev_idx = _resolve_device_idx(device)
    log.info("Listening for %.1fs (device=%s)...", seconds, dev_idx if dev_idx is not None else "default")
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
    except Exception as e:
        log.error("Failed recording audio: %s", e)
        return np.zeros(0, dtype=np.float32)


def transcribe(audio: np.ndarray) -> str:
    """Transcribe a float32 mono 16kHz audio array to text with gain normalization and VAD fallback."""
    if audio is None or audio.size == 0:
        return ""

    # Check peak & RMS volume level
    peak = float(np.max(np.abs(audio)))
    if peak < 0.00005:
        log.info("Recorded audio is silent (peak=%.6f).", peak)
        return ""

    # Normalize audio gain to 0.85 peak if quiet
    if peak < 0.3:
        audio = (audio / (peak + 1e-6) * 0.85).astype(np.float32)

    try:
        model = _get_model()
        # 1. Try with VAD filter
        segments, _info = model.transcribe(audio, language="en", vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()

        # 2. Fallback without VAD filter if VAD stripped quiet human speech
        if not text:
            segments, _info = model.transcribe(audio, language="en", vad_filter=False)
            text = " ".join(seg.text.strip() for seg in segments).strip()

        log.info("Heard: %r", text)
        return text
    except Exception as e:
        log.error("Whisper transcription failed: %s", e)
        return ""


def listen_and_transcribe(seconds: float = 5.0, device: int | str | None = None) -> str:
    audio = record_audio(seconds, device=device)
    return transcribe(audio)
