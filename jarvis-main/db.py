"""
Local SQLite store for JARVIS tasks and reminders. No server, single file DB.
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "jarvis.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    due_at REAL,              -- unix timestamp, NULL = no due time
    done INTEGER NOT NULL DEFAULT 0,
    notified INTEGER NOT NULL DEFAULT 0  -- reminder already spoken?
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def _format_time(ts: float | None) -> str | None:
    if ts is None:
        return None
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%b %d, %H:%M")


def _relative_due_str(due_at: float | None) -> str | None:
    if due_at is None:
        return None
    now = time.time()
    diff = due_at - now
    if diff <= 0:
        return "due now"
    mins = int(diff // 60)
    if mins < 60:
        return f"in {mins}m"
    hours = mins // 60
    if hours < 24:
        return f"in {hours}h {mins % 60}m"
    days = hours // 24
    return f"in {days}d"


def add_task(text: str, due_minutes: float | None = None) -> int:
    """Add a task, optionally with a reminder `due_minutes` from now. Returns task id."""
    now = time.time()
    due_at = now + due_minutes * 60 if due_minutes and due_minutes > 0 else None
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO tasks (text, created_at, due_at) VALUES (?, ?, ?)",
            (text.strip(), now, due_at),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_tasks(include_done: bool = False) -> list[dict]:
    conn = _conn()
    try:
        q = "SELECT id, text, created_at, due_at, done, notified FROM tasks"
        if not include_done:
            q += " WHERE done = 0"
        q += " ORDER BY done ASC, COALESCE(due_at, created_at) ASC"
        rows = conn.execute(q).fetchall()
        result = []
        for r in rows:
            created_ts = r[2]
            due_ts = r[3]
            result.append(
                {
                    "id": r[0],
                    "text": r[1],
                    "created_at": created_ts,
                    "created_at_formatted": _format_time(created_ts),
                    "due_at": due_ts,
                    "due_at_formatted": _format_time(due_ts),
                    "due_relative": _relative_due_str(due_ts),
                    "done": bool(r[4]),
                    "notified": bool(r[5]),
                }
            )
        return result
    finally:
        conn.close()


def complete_task(task_id: int) -> bool:
    conn = _conn()
    try:
        cur = conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_task(task_id: int) -> bool:
    """Permanently delete a task by id."""
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def clear_completed_tasks() -> int:
    """Clear all finished tasks. Returns count of deleted tasks."""
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE done = 1")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def due_unnotified_reminders(now: float | None = None) -> list[dict]:
    """Reminders whose due_at has passed and haven't been spoken yet."""
    now = now if now is not None else time.time()
    conn = _conn()
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
    conn = _conn()
    try:
        conn.execute("UPDATE tasks SET notified = 1 WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()
