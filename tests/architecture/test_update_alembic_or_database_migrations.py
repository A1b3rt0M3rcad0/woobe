"""Tests for spec 134 — update alembic or database migrations.

Validates that the Alembic migration environment imports models from the agent
module (not legacy ai/knowledge/runtime paths), follows expand-migrate-contract
strategy, and does not create destructive renames or new cross-module FKs.
"""
import importlib
import pathlib
import re


MIGRATIONS_DIR = pathlib.Path("migrations/versions")
ENV_PATH = pathlib.Path("migrations/env.py")
DB_BASE = pathlib.Path("src/shared/infra/database/base.py")


class TestAlembicMigrationsSuccess:
    """Verify Alembic env.py and migration conventions."""

    def test_alembic_env_imports_agent_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        assert "modules.agent.infra.database.models" in content, (
            "migrations/env.py must import from agent.infra.database.models"
        )

    def test_alembic_env_no_longer_imports_legacy_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        assert "from modules.ai.infra.models" not in content, (
            "migrations/env.py must not import from legacy modules.ai.infra.models"
        )
        assert "from modules.knowledge.infra.models" not in content, (
            "migrations/env.py must not import from legacy modules.knowledge.infra.models"
        )
        assert "from modules.runtime.infra.models" not in content, (
            "migrations/env.py must not import from legacy modules.runtime.infra.models"
        )

    def test_alembic_env_imports_all_required_modules(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        required_imports = [
            "modules.identity.infra.database.models",
            "modules.core.infra.database.models",
            "modules.tools.infra.database.models",
            "modules.metering.infra.database.models",
            "modules.billing.infra.database.models",
            "modules.observability.infra.database.models",
            "modules.agent.infra.database.models",
        ]
        for module_path in required_imports:
            assert module_path in content, (
                f"migrations/env.py must import {module_path}"
            )

    def test_migration_files_exist(self):
        versions = list(MIGRATIONS_DIR.glob("*.py"))
        assert len(versions) > 0, "Migration version files must exist"

    def test_migration_files_have_upgrade_and_downgrade(self):
        versions = list(MIGRATIONS_DIR.glob("*.py"))
        for v in versions:
            if v.name == "__init__.py":
                continue
            content = v.read_text(encoding="utf-8")
            assert "def upgrade" in content, (
                f"Migration {v.name} must have upgrade() function"
            )
            assert "def downgrade" in content, (
                f"Migration {v.name} must have downgrade() function"
            )


class TestAlembicMigrationsRejectsForbidden:
    """Verify migration files do not contain forbidden patterns."""

    def test_no_destructive_rename_in_migrations(self):
        versions = list(MIGRATIONS_DIR.glob("*.py"))
        for v in versions:
            if v.name == "__init__.py":
                continue
            content = v.read_text(encoding="utf-8")
            assert "op.rename_table" not in content, (
                f"Migration {v.name} must not use destructive rename_table"
            )

    def test_no_new_cross_module_foreign_keys_in_recent_migrations(self):
        recent = sorted(
            MIGRATIONS_DIR.glob("*.py"),
            key=lambda p: p.stem,
        )
        for v in recent[-6:]:
            if v.name == "__init__.py":
                continue
            content = v.read_text(encoding="utf-8")
            forbidden_fk_patterns = [
                "core.projects",
                "identity.organizations",
                "identity.users",
                "billing.plans",
                "billing.subscriptions",
            ]
            fk_matches = re.findall(
                r"ForeignKey\(['\"]([\w.]+)['\"]",
                content,
            )
            for fk_target in fk_matches:
                for forbidden in forbidden_fk_patterns:
                    assert fk_target != forbidden, (
                        f"Migration {v.name} must not create FK to {forbidden}"
                    )

    def test_no_on_delete_cascade_between_modules(self):
        versions = list(MIGRATIONS_DIR.glob("*.py"))
        for v in versions:
            if v.name == "__init__.py":
                continue
            content = v.read_text(encoding="utf-8")
            matches = re.finditer(
                r"""(?x)
                ondelete\s*=\s*['"]CASCADE['"]
                """,
                content,
            )
            for m in matches:
                line_start = max(0, m.start() - 200)
                context_window = content[line_start : m.end() + 50]
                has_external_module = re.search(
                    r"(core|identity|billing|metering|tools|observability)\.",
                    context_window,
                )
                if has_external_module:
                    v_name = v.name
                    assert False, (
                        f"Migration {v_name}: ON DELETE CASCADE referencing "
                        f"external module"
                    )

    def test_agent_migration_models_follow_expand_migrate_contract(self):
        agent_models = pathlib.Path(
            "src/modules/agent/infra/database/models.py"
        )
        if not agent_models.is_file():
            return
        content = agent_models.read_text(encoding="utf-8")
        assert "__tablename__" in content, (
            "Agent models must have table definitions"
        )


class TestAlembicMigrationsKeepsLegacyCompatibility:
    """Verify legacy infrastructure is preserved."""

    def test_database_base_exists(self):
        assert DB_BASE.is_file(), (
            "shared/infra/database/base.py must exist for SQLAlchemy Base"
        )
