from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
UOW_FILE = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core" / "infra" / "database" / "unit_of_work.py"


class TestCoreOutboxAtomicity:
    def test_uow_wraps_outbox_in_transaction(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "if exc_type is not None:\n            await self.rollback()" in content or \
               "if exc_type is not None:\n            await self.rollback()" in content.replace("            ", "        "), \
            "UoW must rollback on exception to preserve Outbox atomicity"

    def test_commit_handles_pending_rollback(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "PendingRollbackError" in content, \
            "UoW must handle PendingRollbackError during commit"

    def test_rollback_clears_session_state(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "async def rollback" in content
        assert "await self._session.rollback()" in content
