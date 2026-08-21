"""
Security & Permission Manager for JARVIS AI OS.

Implements centralized security and permission management for sensitive actions:
  - System Control (Shutdown, Restart, Lock)
  - Browser Automation
  - File System Operations
  - Camera & Vision
  - External Application Execution
  - Desktop Controls

Dangerous operations require explicit user confirmation before execution.
Permissions can be checked, granted, remembered (persistent), or revoked.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from enum import Enum
from typing import Any

from jarvis.core.config import memory_db_path
from jarvis.core.event_bus import bus

log = logging.getLogger("jarvis.security")


class PermissionCategory(str, Enum):
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    SYSTEM_RESTART = "SYSTEM_RESTART"
    SYSTEM_LOCK = "SYSTEM_LOCK"
    BROWSER_AUTOMATION = "BROWSER_AUTOMATION"
    APP_LAUNCH = "APP_LAUNCH"
    APP_KILL = "APP_KILL"
    FILE_ACCESS = "FILE_ACCESS"
    CAMERA_VISION = "CAMERA_VISION"
    MICROPHONE = "MICROPHONE"
    EMAIL_SEND = "EMAIL_SEND"
    FORM_SUBMISSION = "FORM_SUBMISSION"
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    ACCOUNT_SETTINGS = "ACCOUNT_SETTINGS"
    PURCHASE_ACTION = "PURCHASE_ACTION"
    CONTENT_DELETION = "CONTENT_DELETION"


# Actions that are inherently sensitive/dangerous and MUST require confirmation before execution
DANGEROUS_ACTIONS: set[PermissionCategory] = {
    PermissionCategory.SYSTEM_SHUTDOWN,
    PermissionCategory.SYSTEM_RESTART,
    PermissionCategory.EMAIL_SEND,
    PermissionCategory.FORM_SUBMISSION,
    PermissionCategory.FILE_UPLOAD,
    PermissionCategory.ACCOUNT_SETTINGS,
    PermissionCategory.PURCHASE_ACTION,
    PermissionCategory.CONTENT_DELETION,
}

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS permissions (
    category TEXT PRIMARY KEY,
    granted INTEGER NOT NULL DEFAULT 0,
    requires_confirmation INTEGER NOT NULL DEFAULT 1,
    last_requested REAL,
    updated_at REAL NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(memory_db_path())
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_SCHEMA)
    return conn


class PermissionManager:
    """Centralized Security Agent & Permission Manager."""

    def __init__(self) -> None:
        self._pending_confirmations: dict[str, dict[str, Any]] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize default permission policies."""
        conn = _get_conn()
        try:
            now = time.time()
            defaults = [
                (PermissionCategory.SYSTEM_SHUTDOWN.value, 0, 1),
                (PermissionCategory.SYSTEM_RESTART.value, 0, 1),
                (PermissionCategory.SYSTEM_LOCK.value, 1, 0),
                (PermissionCategory.BROWSER_AUTOMATION.value, 1, 0),
                (PermissionCategory.APP_LAUNCH.value, 1, 0),
                (PermissionCategory.APP_KILL.value, 1, 0),
                (PermissionCategory.FILE_ACCESS.value, 1, 0),
                (PermissionCategory.CAMERA_VISION.value, 1, 0),
                (PermissionCategory.MICROPHONE.value, 1, 0),
                (PermissionCategory.EMAIL_SEND.value, 0, 1),
                (PermissionCategory.FORM_SUBMISSION.value, 0, 1),
                (PermissionCategory.FILE_UPLOAD.value, 0, 1),
                (PermissionCategory.FILE_DOWNLOAD.value, 1, 0),
                (PermissionCategory.ACCOUNT_SETTINGS.value, 0, 1),
                (PermissionCategory.PURCHASE_ACTION.value, 0, 1),
                (PermissionCategory.CONTENT_DELETION.value, 0, 1),
            ]
            for cat, granted, req_conf in defaults:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (category, granted, requires_confirmation, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (cat, granted, req_conf, now),
                )
            conn.commit()
        finally:
            conn.close()

    def is_granted(self, category: PermissionCategory) -> bool:
        """Check if permission is granted in storage."""
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT granted, requires_confirmation FROM permissions WHERE category = ?",
                (category.value,),
            ).fetchone()
            if not row:
                return True
            granted, requires_conf = bool(row[0]), bool(row[1])
            # If it requires confirmation, it is not auto-granted
            if requires_conf:
                return False
            return granted
        finally:
            conn.close()

    def set_permission(self, category: PermissionCategory, granted: bool, requires_confirmation: bool = False) -> None:
        """Update permission state."""
        conn = _get_conn()
        try:
            now = time.time()
            conn.execute(
                "INSERT OR REPLACE INTO permissions (category, granted, requires_confirmation, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (category.value, int(granted), int(requires_confirmation), now),
            )
            conn.commit()
            log.info("Permission for %s set: granted=%s, requires_confirmation=%s", category.value, granted, requires_confirmation)
        finally:
            conn.close()

    def get_all_permissions(self) -> list[dict[str, Any]]:
        """Return list of all permissions."""
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT category, granted, requires_confirmation, updated_at FROM permissions").fetchall()
            return [
                {
                    "category": r[0],
                    "granted": bool(r[1]),
                    "requires_confirmation": bool(r[2]),
                    "updated_at": r[3],
                }
                for r in rows
            ]
        finally:
            conn.close()

    async def request_action_permission(
        self,
        category: PermissionCategory,
        description: str,
        action_payload: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """
        Request permission to perform an action.
        Returns: (allowed: bool, prompt_or_reason: str)
        """
        # If dangerous, require confirmation
        if category in DANGEROUS_ACTIONS or not self.is_granted(category):
            conf_id = f"{category.value}_{int(time.time()*1000)}"
            self._pending_confirmations[conf_id] = {
                "category": category.value,
                "description": description,
                "payload": action_payload or {},
                "timestamp": time.time(),
            }
            await bus.emit("permission:required", {
                "id": conf_id,
                "category": category.value,
                "description": description,
            })
            log.warning("Security check required for '%s': %s", category.value, description)
            return False, f"Sir, {description}. Do you want me to continue?"

        return True, "Permission granted"

    def confirm_action(self, confirmation_id: str) -> dict[str, Any] | None:
        """Confirm a pending dangerous action."""
        if confirmation_id in self._pending_confirmations:
            item = self._pending_confirmations.pop(confirmation_id)
            log.info("Action %s confirmed.", confirmation_id)
            bus.emit_sync("permission:granted", {"id": confirmation_id, "category": item["category"]})
            return item
        return None

    def reject_action(self, confirmation_id: str) -> None:
        """Reject a pending dangerous action."""
        if confirmation_id in self._pending_confirmations:
            self._pending_confirmations.pop(confirmation_id)
            log.info("Action %s rejected.", confirmation_id)
            bus.emit_sync("permission:denied", {"id": confirmation_id})

    def has_pending_confirmation(self) -> bool:
        return bool(self._pending_confirmations)

    def get_pending(self) -> dict[str, dict[str, Any]]:
        return dict(self._pending_confirmations)

    def clear_expired_pending(self, timeout_seconds: float = 60.0) -> None:
        now = time.time()
        expired = [
            cid for cid, item in self._pending_confirmations.items()
            if now - item.get("timestamp", now) > timeout_seconds
        ]
        for cid in expired:
            self._pending_confirmations.pop(cid, None)


# Module-level singleton
permission_manager = PermissionManager()
