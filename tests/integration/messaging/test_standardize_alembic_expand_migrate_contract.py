"""Integration tests for spec 098 — standardize alembic expand-migrate contract.

Validates that alembic env.py uses canonical module paths, all migrations
have upgrade/downgrade, and no destructive operations exist.
"""
from __future__ import annotations

import pathlib

MIGRATIONS_DIR = pathlib.Path("migrations/versions")
ENV_PATH = pathlib.Path("migrations/env.py")


def test_env_imports_all_canonical_modules():
    """env.py must import models from all 7 canonical modules."""
    content = ENV_PATH.read_text(encoding="utf-8")
    modules = ["identity", "core", "agent", "tools", "metering", "billing", "observability"]
    for mod in modules:
        path = f"modules.{mod}.infra.database.models"
        assert path in content, (
            f"env.py missing import for {path}"
        )


def test_env_no_legacy_imports():
    """env.py must not import from legacy ai/knowledge/runtime paths."""
    content = ENV_PATH.read_text(encoding="utf-8")
    assert "modules.ai" not in content
    assert "modules.knowledge" not in content
    assert "modules.runtime" not in content


def test_migration_files_have_upgrade_and_downgrade():
    """Every migration version must define upgrade() and downgrade()."""
    versions = sorted(MIGRATIONS_DIR.glob("[0-9]*.py"))
    assert len(versions) > 0, "No migration version files found"
    for v in versions:
        content = v.read_text(encoding="utf-8")
        assert "def upgrade()" in content, (
            f"{v.name} missing upgrade()"
        )
        assert "def downgrade()" in content, (
            f"{v.name} missing downgrade()"
        )


def test_no_destructive_rename_in_migrations():
    """No migration should use destructive rename_table."""
    for v in MIGRATIONS_DIR.glob("*.py"):
        if v.name == "__init__.py":
            continue
        content = v.read_text(encoding="utf-8")
        assert "op.rename_table" not in content, (
            f"{v.name} uses destructive rename_table"
        )


def test_env_imports_base_from_canonical_path():
    """env.py must import Base from shared.infra.database.base."""
    content = ENV_PATH.read_text(encoding="utf-8")
    assert "shared.infra.database.base" in content, (
        "env.py must import Base from canonical path"
    )
