"""
Unified configuration management for JARVIS AI OS.

Loads environment from .env, validates required keys, and provides
centralised access to all configuration values with secure masking
for log output.  Every subsystem reads its settings through this
module so there is exactly one source of truth.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

log = logging.getLogger("jarvis.config")

# ---------------------------------------------------------------------------
# Locate and load .env
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # jarvis-assistant-v2/
_ENV_SEARCH_PATHS = [
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "jarvis-main" / ".env",
]

_loaded = False


def load_env() -> None:
    """Load the first .env file found in the search paths."""
    global _loaded
    if _loaded:
        return
    for p in _ENV_SEARCH_PATHS:
        if p.is_file():
            load_dotenv(p)
            log.info("Loaded environment from %s", p)
            _loaded = True
            return
    log.warning("No .env file found — relying on shell environment variables.")
    _loaded = True


def _env(key: str, default: str = "") -> str:
    load_env()
    return (os.environ.get(key) or default).strip()


# ---------------------------------------------------------------------------
# Masked helpers (never print full secrets)
# ---------------------------------------------------------------------------


def _mask(value: str, visible: int = 4) -> str:
    if not value or len(value) <= visible:
        return "***"
    return value[:visible] + "…" + "*" * 8


# ---------------------------------------------------------------------------
# API Keys & AI Models
# ---------------------------------------------------------------------------

def gemini_api_key() -> str:
    """Return Google Gemini API key if configured."""
    return _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")


def gemini_model() -> str:
    """Default Gemini model: gemini-2.5-flash / gemini-2.0-flash / gemini-1.5-flash."""
    return _env("GEMINI_MODEL", "gemini-2.5-flash")


def anthropic_api_key() -> str:
    """Fallback Anthropic Claude API key."""
    return _env("ANTHROPIC_API_KEY")


def anthropic_model() -> str:
    return _env("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")


def elevenlabs_api_key() -> str:
    return _env("ELEVENLABS_API_KEY")


def elevenlabs_voice_id() -> str:
    return _env("ELEVENLABS_VOICE_ID")


def elevenlabs_model_id() -> str:
    return _env("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")


def elevenlabs_output_format() -> str:
    return _env("ELEVENLABS_OUTPUT_FORMAT", "pcm_24000")


def elevenlabs_pcm_sample_rate() -> int:
    override = _env("ELEVENLABS_PCM_SAMPLE_RATE")
    if override.isdigit():
        return int(override)
    fmt = elevenlabs_output_format()
    if fmt.startswith("pcm_"):
        try:
            return int(fmt.split("_", maxsplit=1)[1])
        except (ValueError, IndexError):
            pass
    return 24000


# ---------------------------------------------------------------------------
# Languages & Voice Behavior
# ---------------------------------------------------------------------------

def default_language() -> str:
    return _env("JARVIS_DEFAULT_LANG", "en")


def secondary_language() -> str:
    return _env("JARVIS_SECONDARY_LANG", "ta")


def wake_word() -> str:
    return _env("JARVIS_WAKE_WORD", "jarvis").lower()


def conversation_timeout_seconds() -> float:
    try:
        return float(_env("JARVIS_CONVERSATION_TIMEOUT", "120.0"))
    except ValueError:
        return 120.0


# ---------------------------------------------------------------------------
# Voice / Audio
# ---------------------------------------------------------------------------

def input_device() -> str | None:
    val = _env("JARVIS_INPUT_DEVICE")
    return val if val else None


def listen_seconds() -> float:
    try:
        return float(_env("JARVIS_LISTEN_SECONDS", "5.0"))
    except ValueError:
        return 5.0


def whisper_model_name() -> str:
    # Multilingual 'base' is standard for English + Tamil detection
    return _env("JARVIS_WHISPER_MODEL", "base")


def voice_cooldown_seconds() -> float:
    try:
        return float(_env("JARVIS_VOICE_COOLDOWN_S", "3.0"))
    except ValueError:
        return 3.0


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def web_port() -> int:
    try:
        return int(_env("JARVIS_WEB_PORT", "8000"))
    except ValueError:
        return 8000


def auto_open_browser() -> bool:
    return _env("JARVIS_AUTO_OPEN_WEB", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------

def data_dir() -> Path:
    d = _PROJECT_ROOT / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "jarvis.db"


def memory_db_path() -> Path:
    return data_dir() / "memory.db"


def tts_cache_dir() -> Path:
    d = data_dir() / "tts_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Site aliases (used by browser/commander)
# ---------------------------------------------------------------------------

SITE_ALIASES: dict[str, str] = {
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "google": "https://google.com",
    "gmail": "https://mail.google.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "linkedin": "https://www.linkedin.com",
    "stackoverflow": "https://stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai/new",
}


# ---------------------------------------------------------------------------
# Desktop app map (Windows)
# ---------------------------------------------------------------------------

DESKTOP_APPS: dict[str, str] = {
    "chrome": "chrome",
    "browser": "chrome",
    "vscode": "code",
    "vs code": "code",
    "cursor": "cursor",
    "antigravity": "antigravity",
    "whatsapp": "whatsapp:",
    "telegram": "telegram:",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "notepad": "notepad.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "cmd": "cmd.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "spotify": "spotify:",
}


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def validate_startup() -> dict[str, Any]:
    """Return a report dict summarising key configuration status."""
    g_key = gemini_api_key()
    a_key = anthropic_api_key()
    e_key = elevenlabs_api_key()

    report: dict[str, Any] = {
        "gemini_configured": bool(g_key) and not g_key.startswith("your_"),
        "anthropic_configured": bool(a_key) and not a_key.startswith("your_"),
        "elevenlabs_configured": bool(e_key) and bool(elevenlabs_voice_id()),
        "whisper_model": whisper_model_name(),
        "primary_model": gemini_model() if g_key else (anthropic_model() if a_key else "local_dynamic_fallback"),
        "default_lang": default_language(),
        "secondary_lang": secondary_language(),
        "web_port": web_port(),
        "data_dir": str(data_dir()),
    }
    for k, v in report.items():
        if "key" in k.lower() or "secret" in k.lower():
            continue
        log.info("Config %-25s = %s", k, v)

    if not report["gemini_configured"] and not report["anthropic_configured"]:
        log.warning("No LLM API key configured (Gemini/Anthropic) — using local dynamic AI engine fallback.")
    if not report["elevenlabs_configured"]:
        log.warning("ElevenLabs credentials missing — TTS will use local SAPI5 fallback.")
    return report
