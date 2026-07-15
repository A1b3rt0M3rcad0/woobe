from pathlib import Path


def test_network_session_title_migration_is_linear_after_0047() -> None:
    source = Path(
        "migrations/versions/0048_network_session_titles.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "0048"' in source
    assert 'down_revision: str | None = "0047"' in source
    assert "trg_network_session_title_from_first_message" in source
    assert "rename_automatic_network_session" in source
    assert "DISTINCT ON (network_session_id)" in source
    assert "previous_message.role = 'user'" in source
