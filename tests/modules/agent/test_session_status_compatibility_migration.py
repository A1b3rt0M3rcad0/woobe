"""Regression coverage for legacy Agent Session status normalization."""

import importlib.util
import inspect
from pathlib import Path

from modules.agent.domain.enums import SessionStatus


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "migrations"
    / "versions"
    / "0061_normalize_agent_session_statuses.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "woobe_agent_migration_0061", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_status_migration_revision_chain() -> None:
    migration = _migration()
    assert migration.revision == "0061"
    assert migration.down_revision == "0060"


def test_session_status_migration_matches_current_domain_contract() -> None:
    migration = _migration()
    assert migration.VALID_SESSION_STATUSES == tuple(
        status.value for status in SessionStatus
    )
    assert "archived" not in migration.VALID_SESSION_STATUSES


def test_upgrade_normalizes_archived_before_enforcing_constraint() -> None:
    source = inspect.getsource(_migration().upgrade)

    normalization_position = source.index("UPDATE agent.sessions")
    constraint_position = source.index("create_check_constraint")

    assert normalization_position < constraint_position
    assert "LOWER(status) = 'archived'" in source
    assert "SET status = 'closed'" in source
    assert '"ck_agent_sessions_status"' in source


def test_upgrade_keeps_unknown_session_statuses_strict() -> None:
    source = inspect.getsource(_migration().upgrade)

    assert "except" not in source
    assert "fallback" not in source.lower()
    assert "create_check_constraint" in source


def test_downgrade_does_not_recreate_legacy_archived_state() -> None:
    source = inspect.getsource(_migration().downgrade)

    assert "drop_constraint" in source
    assert '"ck_agent_sessions_status"' in source
    assert "UPDATE agent.sessions" not in source
