"""Tests for migration 0057: pending Project access attached to invitations."""

import importlib


def _get_migration():
    return importlib.import_module(
        "migrations.versions.0057_add_pending_project_invite_access"
    )


def test_migration_revision_chain():
    migration = _get_migration()
    assert migration.revision == "0057"
    assert migration.down_revision == "0056"


def test_migration_declares_pending_invite_access_table():
    migration = _get_migration()
    source = open(migration.__file__, encoding="utf-8").read()
    assert '"project_invite_access"' in source
    assert '"workspace_invite_id"' in source
    assert '"project_id"' in source
    assert '"status"' in source
    assert "uq_core_project_invite_access_project_invite" in source
