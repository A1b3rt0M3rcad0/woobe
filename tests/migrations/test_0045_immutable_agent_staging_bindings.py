from pathlib import Path


def test_immutable_agent_staging_migration_is_linear_after_0044() -> None:
    source = Path(
        "migrations/versions/0045_immutable_agent_staging_bindings.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0045"' in source
    assert 'down_revision: str | None = "0044"' in source
    assert '"snapshot_kind"' in source
    assert '"uq_agent_releases_staging"' in source
    assert '"ck_agent_releases_snapshot_kind"' in source
    assert "status = 'staging'" in source
    assert "DROP INDEX IF EXISTS agent.uq_agent_releases_staging" in source
