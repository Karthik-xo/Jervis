"""
Double-clap wake detector, factored out of original jarvis.py for reusability.
Includes mic input resolution and audio level calculations.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Callable

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.clap")

SAMPLE_RATE = 44100
BLOCK_MS = 40
CHANNELS = 1

SPIKE_RATIO = 7.0
COOLDOWN_S = 0.45
MIN_DOUBLE_GAP_S = 0.05
MAX_DOUBLE_GAP_S = 0.35
RETRIGGER_RATIO = 0.55
NOISE_FLOOR_ALPHA = 0.992
MIN_RMS = 0.012
QUIET_GATE_MULT = 2.2


def _block_samples() -> int:
    return max(int(SAMPLE_RATE * BLOCK_MS / 1000), 1)


def rms_mono(block: np.ndarray) -> float:
    block = block.astype(np.float64)
    if block.ndim > 1:
        block = np.mean(block, axis=1)
    return float(np.sqrt(np.mean(block**2))) if block.size else 0.0


def resolve_input_device(device_spec: int | str | None = None) -> int | None:
    if isinstance(device_spec, int):
        return device_spec
    spec = (device_spec or os.environ.get("JARVIS_INPUT_DEVICE") or "").strip()
    if not spec:
        return None
    if spec.isdigit():
        return int(spec)
    needle = spec.lower()
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] >= 1 and needle in dev["name"].lower():
            return idx
    log.warning("No input device matches spec: %r", spec)
    return None


def listen_for_double_claps(
    on_double_clap: Callable[[], None],
    device: int | str | None = None,
    stop_event: object | None = None,
) -> None:
    """Listens for double claps and triggers `on_double_clap()` in a new thread."""
    import threading

    device_idx = resolve_input_device(device)
    blocksize = _block_samples()
    noise_floor = 1e-4
    last_logged_double = 0.0
    first_clap_time: float | None = None
    spike_armed = True

    log.info(
        "Listening for double claps (device=%s, rate=%d, block=%dms, spike_ratio=%.1f).",
        device_idx if device_idx is not None else "default",
        SAMPLE_RATE,
        BLOCK_MS,
        SPIKE_RATIO,
    )

    try:
        with sd.InputStream(
            device=device_idx,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=blocksize,
        ) as stream:
            while True:
                if stop_event and getattr(stop_event, "is_set", lambda: False)():
                    break
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    log.warning("Input overflow; try a larger BLOCK_MS")

                level = rms_mono(data)
                quiet_gate = noise_floor * QUIET_GATE_MULT
                if level < quiet_gate:
                    noise_floor = NOISE_FLOOR_ALPHA * noise_floor + (
                        1.0 - NOISE_FLOOR_ALPHA
                    ) * level
                    noise_floor = max(noise_floor, 1e-7)

                threshold = max(noise_floor * SPIKE_RATIO, MIN_RMS)
                now = time.monotonic()
                retrigger_level = threshold * RETRIGGER_RATIO

                if level < retrigger_level:
                    spike_armed = True

                if (
                    spike_armed
                    and level >= threshold
                    and (now - last_logged_double) >= COOLDOWN_S
                ):
                    spike_armed = False
                    if first_clap_time is None:
                        first_clap_time = now
                    else:
                        gap = now - first_clap_time
                        if gap < MIN_DOUBLE_GAP_S:
                            pass
                        elif gap <= MAX_DOUBLE_GAP_S:
                            first_clap_time = None
                            last_logged_double = now
                            log.info("Double clap detected (gap=%.3fs).", gap)
                            threading.Thread(
                                target=on_double_clap, daemon=True
                            ).start()
                        else:
                            first_clap_time = now
    except Exception as e:
        log.error("Clap detection error: %s", e)
