# JARVIS v2 — voice command assistant

Adds a real "brain" on top of the original clap-trigger script. The original
`jarvis.py` (fixed macro: clap → Spotify + Chrome + Cursor) is untouched and still
works standalone. This is a separate entrypoint, `jarvis_assistant.py`, that instead
listens to what you actually say.

## Flow
Double clap → record ~5s of audio → transcribe locally with Whisper → send to
Claude with a small toolset → Claude decides an action (open a site, save a task,
list tasks, etc.) → the action runs → the reply is spoken back via ElevenLabs.

A background thread also checks every 30s for reminders that came due and speaks them,
even if you haven't clapped.

## New files
| File | Role |
|---|---|
| `jarvis_assistant.py` | Entrypoint: wires clap → STT → brain → TTS together |
| `clap_detect.py` | Double-clap wake detector (same tuning as original `jarvis.py`, factored out so it's reusable) |
| `stt.py` | Records mic audio, transcribes locally with `faster-whisper` |
| `brain.py` | Sends the transcript to Claude with a toolset (`open_url`, `open_app`, `add_task`, `list_tasks`, `complete_task`) and executes whatever it calls |
| `tts.py` | Speaks any text via ElevenLabs, with the same WAV caching as the original welcome-line code |
| `scheduler.py` | Background thread that polls `db.py` for due reminders |
| `db.py` | SQLite store for tasks/reminders (`jarvis.db`, created automatically) |

## Setup
```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` (or add to your existing one) and fill in:
```env
ANTHROPIC_API_KEY=your_anthropic_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

## Run
```bash

```
Double-clap, then speak a command within ~5 seconds (configurable via
`JARVIS_LISTEN_SECONDS`). Examples:
- "Remind me to follow up with the client in twenty minutes"
- "Open my trading dashboard"
- "What's on my task list"
- "Mark task 2 done"

## Extending it
- **Site aliases** — edit `SITE_ALIASES` in `brain.py` to map phrases like
  "trading dashboard" to real URLs.
- **New tools** — add an entry to `TOOLS` in `brain.py` plus a branch in
  `_execute_tool()`. Claude will start using it automatically once it exists.
- **Better STT accuracy** — swap `"base.en"` for `"small.en"` in `stt.py`
  (`_get_model()`) if base is mis-hearing you; costs a bit more CPU/RAM.
- **Wake word instead of clap** — clap detection can be flaky in noisy rooms;
  `openWakeWord` or Porcupine are drop-in replacements for `clap_detect.py`
  if you want a spoken "Hey Jarvis" trigger later.

## Notes
- The original `jarvis.py` script and its `.env` variables are unchanged — you can
  still run it directly for the old clap-macro behavior.
- Whisper model download happens once on first run (needs the `pythonhosted.org`
  domain reachable) and is cached locally after that.
- First model load takes a few seconds; that's expected.








