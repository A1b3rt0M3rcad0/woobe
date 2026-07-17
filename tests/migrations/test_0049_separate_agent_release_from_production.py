from pathlib import Path


def test_agent_release_activation_migration_is_linear_after_0048() -> None:
    source = Path(
        "migrations/versions/0049_separate_agent_release_from_production.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0049"' in source
    assert 'down_revision: str | None = "0048"' in source
    assert "snapshot_kind = 'release'" in source
    assert "status IN ('archived', 'rolled_back')" in source
    assert "SET status = 'released'" in source
