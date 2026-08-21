"""
Persistent Memory Engine for JARVIS AI OS.

Provides local SQLite-backed storage for:
  - Tasks & reminders (migrated from legacy db.py)
  - User preferences & notes
  - Session / conversation history
  - Frequently used actions
  - Indexed key-value context summaries

All data lives on-disk with fast indexed retrieval, automatic old-session
cleanup, and context summarisation helpers.
"""

from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from jarvis.core.config import db_path, memory_db_path

log = logging.getLogger("jarvis.memory")

# ── Schema ──────────────────────────────────────────────────────────────────

_TASKS_SCHEMA = """\
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    due_at      REAL,
    done        INTEGER NOT NULL DEFAULT 0,
    notified    INTEGER NOT NULL DEFAULT 0
);
"""

_MEMORY_SCHEMA = """\
CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS session_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT    NOT NULL,  -- 'user' | 'assistant'
    content     TEXT    NOT NULL,
    timestamp   REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    content     TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    tags        TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS action_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,
    count       INTEGER NOT NULL DEFAULT 1,
    last_used   REAL    NOT NULL
);
"""

# ── Connection helpers ──────────────────────────────────────────────────────

def _task_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_TASKS_SCHEMA)
    return conn


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(memory_db_path())
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_MEMORY_SCHEMA)
    return conn


# ── Time formatting ─────────────────────────────────────────────────────────

def _format_time(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.datetime.fromtimestamp(ts).strftime("%b %d, %H:%M")


def _relative_due(due_at: float | None) -> str | None:
    if due_at is None:
        return None
    diff = due_at - time.time()
    if diff <= 0:
        return "due now"
    mins = int(diff // 60)
    if mins < 60:
        return f"in {mins}m"
    hours = mins // 60
    if hours < 24:
        return f"in {hours}h {mins % 60}m"
    return f"in {hours // 24}d"


# ═══════════════════════════════════════════════════════════════════════════
#  TASKS & REMINDERS
# ═══════════════════════════════════════════════════════════════════════════

def add_task(text: str, due_minutes: float | None = None) -> int:
    now = time.time()
    due_at = now + due_minutes * 60 if due_minutes and due_minutes > 0 else None
    conn = _task_conn()
    try:
        cur = conn.execute(
            "INSERT INTO tasks (text, created_at, due_at) VALUES (?, ?, ?)",
            (text.strip(), now, due_at),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def list_tasks(include_done: bool = False) -> list[dict]:
    conn = _task_conn()
    try:
        q = "SELECT id, text, created_at, due_at, done, notified FROM tasks"
        if not include_done:
            q += " WHERE done = 0"
        q += " ORDER BY done ASC, COALESCE(due_at, created_at) ASC"
        rows = conn.execute(q).fetchall()
        return [
            {
                "id": r[0],
                "text": r[1],
                "created_at": r[2],
                "created_at_formatted": _format_time(r[2]),
                "due_at": r[3],
                "due_at_formatted": _format_time(r[3]),
                "due_relative": _relative_due(r[3]),
                "done": bool(r[4]),
                "notified": bool(r[5]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def complete_task(task_id: int) -> bool:
    conn = _task_conn()
    try:
        cur = conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_task(task_id: int) -> bool:
    conn = _task_conn()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_completed_tasks() -> int:
    conn = _task_conn()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE done = 1")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def due_unnotified_reminders(now: float | None = None) -> list[dict]:
    now = now if now is not None else time.time()
    conn = _task_conn()
    try:
        rows = conn.execute(
            "SELECT id, text FROM tasks WHERE done = 0 AND notified = 0 "
            "AND due_at IS NOT NULL AND due_at <= ?",
            (now,),
        ).fetchall()
        return [{"id": r[0], "text": r[1]} for r in rows]
    finally:
        conn.close()


def mark_notified(task_id: int) -> None:
    conn = _task_conn()
    try:
        conn.execute("UPDATE tasks SET notified = 1 WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  USER PREFERENCES
# ═══════════════════════════════════════════════════════════════════════════

def set_preference(key: str, value: str) -> None:
    conn = _mem_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_preference(key: str, default: str | None = None) -> str | None:
    conn = _mem_conn()
    try:
        row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default
    finally:
        conn.close()


def all_preferences() -> dict[str, str]:
    conn = _mem_conn()
    try:
        rows = conn.execute("SELECT key, value FROM preferences").fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  SESSION HISTORY (conversation context)
# ═══════════════════════════════════════════════════════════════════════════

_MAX_HISTORY = 50  # Keep last N exchanges


def add_history(role: str, content: str) -> None:
    conn = _mem_conn()
    try:
        conn.execute(
            "INSERT INTO session_history (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, time.time()),
        )
        conn.commit()
        # Auto-cleanup: keep only the most recent entries
        conn.execute(
            "DELETE FROM session_history WHERE id NOT IN "
            "(SELECT id FROM session_history ORDER BY id DESC LIMIT ?)",
            (_MAX_HISTORY,),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(limit: int = 20) -> list[dict]:
    conn = _mem_conn()
    try:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM session_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]
    finally:
        conn.close()


def clear_history() -> None:
    conn = _mem_conn()
    try:
        conn.execute("DELETE FROM session_history")
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  NOTES
# ═══════════════════════════════════════════════════════════════════════════

def add_note(content: str, title: str | None = None, tags: str = "") -> int:
    conn = _mem_conn()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, content, created_at, tags) VALUES (?, ?, ?, ?)",
            (title, content, time.time(), tags),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def list_notes(limit: int = 50) -> list[dict]:
    conn = _mem_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, content, created_at, tags FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "content": r[2], "created_at": r[3], "tags": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_note(note_id: int) -> bool:
    conn = _mem_conn()
    try:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  ACTION FREQUENCY TRACKING
# ═══════════════════════════════════════════════════════════════════════════

def log_action(action: str) -> None:
    """Record that *action* was used (increments counter)."""
    conn = _mem_conn()
    try:
        existing = conn.execute("SELECT count FROM action_log WHERE action = ?", (action,)).fetchone()
        now = time.time()
        if existing:
            conn.execute(
                "UPDATE action_log SET count = count + 1, last_used = ? WHERE action = ?",
                (now, action),
            )
        else:
            conn.execute(
                "INSERT INTO action_log (action, count, last_used) VALUES (?, 1, ?)",
                (action, now),
            )
        conn.commit()
    finally:
        conn.close()


def frequent_actions(limit: int = 10) -> list[dict]:
    conn = _mem_conn()
    try:
        rows = conn.execute(
            "SELECT action, count, last_used FROM action_log ORDER BY count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"action": r[0], "count": r[1], "last_used": r[2]} for r in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
#  CONTEXT SUMMARISATION
# ═══════════════════════════════════════════════════════════════════════════

def summarise_context(max_items: int = 10) -> str:
    """Build a compact context string for the LLM system prompt."""
    parts: list[str] = []

    # Recent conversation
    history = get_history(limit=6)
    if history:
        parts.append("Recent conversation:")
        for h in history:
            parts.append(f"  {h['role']}: {h['content'][:120]}")

    # Pending tasks
    tasks = list_tasks(include_done=False)
    if tasks:
        parts.append(f"Pending tasks ({len(tasks)}):")
        for t in tasks[:5]:
            due = f" [{t['due_relative']}]" if t.get("due_relative") else ""
            parts.append(f"  #{t['id']}: {t['text']}{due}")

    # User preferences
    prefs = all_preferences()
    if prefs:
        parts.append("User preferences:")
        for k, v in list(prefs.items())[:5]:
            parts.append(f"  {k}: {v}")

    return "\n".join(parts) if parts else ""
