"""Tests for Security Agent & Permission Manager."""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jarvis.services.permission_service import (
    permission_manager,
    PermissionCategory,
    DANGEROUS_ACTIONS,
)


class TestPermissionManager:
    def test_dangerous_actions_classified(self):
        assert PermissionCategory.SYSTEM_SHUTDOWN in DANGEROUS_ACTIONS
        assert PermissionCategory.SYSTEM_RESTART in DANGEROUS_ACTIONS

    @pytest.mark.asyncio
    async def test_shutdown_requires_confirmation(self):
        allowed, prompt = await permission_manager.request_action_permission(
            PermissionCategory.SYSTEM_SHUTDOWN,
            "shutting down the computer will close your current session",
        )
        assert allowed is False
        assert "Do you want me to continue" in prompt
        assert permission_manager.has_pending_confirmation()

    def test_confirm_and_reject_flow(self):
        pending = permission_manager.get_pending()
        if pending:
            cid = list(pending.keys())[0]
            item = permission_manager.confirm_action(cid)
            assert item is not None
            assert item["category"] == PermissionCategory.SYSTEM_SHUTDOWN.value

    def test_get_all_permissions(self):
        perms = permission_manager.get_all_permissions()
        assert len(perms) > 0
        categories = [p["category"] for p in perms]
        assert PermissionCategory.APP_LAUNCH.value in categories
