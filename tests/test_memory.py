"""Tests for the persistent Memory engine."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override DB paths to use temp location for testing
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="jarvis_test_")
os.environ["JARVIS_DATA_DIR_OVERRIDE"] = _tmp

from jarvis.core import memory


class TestTasks:
    def test_add_and_list(self):
        tid = memory.add_task("Test task alpha")
        assert tid > 0
        tasks = memory.list_tasks(include_done=True)
        found = [t for t in tasks if t["id"] == tid]
        assert len(found) == 1
        assert found[0]["text"] == "Test task alpha"
        assert not found[0]["done"]
        # Cleanup
        memory.delete_task(tid)

    def test_add_with_due(self):
        tid = memory.add_task("Timed task", due_minutes=10)
        tasks = memory.list_tasks()
        found = [t for t in tasks if t["id"] == tid]
        assert found[0]["due_at"] is not None
        assert found[0]["due_relative"] is not None
        memory.delete_task(tid)

    def test_complete_task(self):
        tid = memory.add_task("Complete me")
        ok = memory.complete_task(tid)
        assert ok
        tasks = memory.list_tasks(include_done=True)
        found = [t for t in tasks if t["id"] == tid]
        assert found[0]["done"]
        memory.delete_task(tid)

    def test_delete_task(self):
        tid = memory.add_task("Delete me")
        ok = memory.delete_task(tid)
        assert ok
        ok2 = memory.delete_task(tid)
        assert not ok2

    def test_clear_completed(self):
        t1 = memory.add_task("Done1")
        t2 = memory.add_task("Done2")
        memory.complete_task(t1)
        memory.complete_task(t2)
        count = memory.clear_completed_tasks()
        assert count >= 2

    def test_due_unnotified(self):
        tid = memory.add_task("Urgent", due_minutes=0.01)
        # Due almost immediately (~0.6s from now)
        reminders = memory.due_unnotified_reminders(now=time.time() + 2)
        ids = [r["id"] for r in reminders]
        assert tid in ids
        memory.mark_notified(tid)
        reminders2 = memory.due_unnotified_reminders(now=time.time() + 1)
        ids2 = [r["id"] for r in reminders2]
        assert tid not in ids2
        memory.delete_task(tid)


class TestPreferences:
    def test_set_and_get(self):
        memory.set_preference("test_key", "test_value")
        val = memory.get_preference("test_key")
        assert val == "test_value"

    def test_get_default(self):
        val = memory.get_preference("nonexistent_key_xyz", default="fallback")
        assert val == "fallback"

    def test_overwrite(self):
        memory.set_preference("overwrite_key", "v1")
        memory.set_preference("overwrite_key", "v2")
        val = memory.get_preference("overwrite_key")
        assert val == "v2"

    def test_all_preferences(self):
        memory.set_preference("all_test_a", "1")
        memory.set_preference("all_test_b", "2")
        prefs = memory.all_preferences()
        assert "all_test_a" in prefs
        assert "all_test_b" in prefs


class TestSessionHistory:
    def test_add_and_get(self):
        memory.clear_history()
        memory.add_history("user", "Hello JARVIS")
        memory.add_history("assistant", "Hello sir")
        history = memory.get_history(limit=5)
        assert len(history) >= 2
        assert history[-2]["role"] == "user"
        assert history[-1]["role"] == "assistant"

    def test_auto_cleanup(self):
        memory.clear_history()
        for i in range(60):
            memory.add_history("user", f"Message {i}")
        history = memory.get_history(limit=100)
        assert len(history) <= 50  # _MAX_HISTORY


class TestNotes:
    def test_add_and_list(self):
        nid = memory.add_note("Test note content", title="Test Note")
        assert nid > 0
        notes = memory.list_notes()
        found = [n for n in notes if n["id"] == nid]
        assert len(found) == 1
        assert found[0]["title"] == "Test Note"
        memory.delete_note(nid)

    def test_delete_note(self):
        nid = memory.add_note("Delete me note")
        ok = memory.delete_note(nid)
        assert ok


class TestActionLog:
    def test_log_action(self):
        memory.log_action("TEST_ACTION")
        memory.log_action("TEST_ACTION")
        freq = memory.frequent_actions()
        found = [a for a in freq if a["action"] == "TEST_ACTION"]
        assert found[0]["count"] >= 2


class TestContextSummary:
    def test_summarise(self):
        memory.add_history("user", "Test context")
        ctx = memory.summarise_context()
        assert isinstance(ctx, str)
