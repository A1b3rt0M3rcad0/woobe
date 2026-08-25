from pathlib import Path

from modules.network.domain.enums import NetworkEnvironment


def test_draft_is_an_internal_network_chat_environment() -> None:
    assert NetworkEnvironment.DRAFT.value == "draft"


def test_live_draft_migration_is_linear_after_0043() -> None:
    source = Path(
        "migrations/versions/0044_enable_live_network_draft_sessions.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "0044"' in source
    assert 'down_revision: str | None = "0043"' in source
    assert "definition_snapshot" in source
    assert "resolved_bindings_snapshot" in source


def test_public_runtime_explicitly_rejects_draft() -> None:
    source = Path(
        "src/modules/network/presentation/public_runtime.py"
    ).read_text(encoding="utf-8")
    assert "Runtime Keys cannot execute a Network Draft" in source
