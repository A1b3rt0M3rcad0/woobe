"""Tests for migration 0056: binary Project access membership."""

import importlib


def _get_migration():
    return importlib.import_module("migrations.versions.0056_add_project_members")


def test_migration_revision_chain():
    migration = _get_migration()
    assert migration.revision == "0056"
    assert migration.down_revision == "0055"


def test_project_member_model_is_binary_access_only():
    from modules.core.infra.database.models import ProjectMemberModel

    columns = ProjectMemberModel.__table__.columns
    assert "project_id" in columns
    assert "user_id" in columns
    assert "status" in columns
    assert "granted_by_user_id" in columns
    assert "role" not in columns
    assert "permissions" not in columns

    constraint_names = {
        constraint.name
        for constraint in ProjectMemberModel.__table__.constraints
        if constraint.name
    }
    assert "uq_core_project_members_project_user" in constraint_names
