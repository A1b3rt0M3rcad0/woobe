"""Architecture checks for the Community Alembic migration environment."""

import pathlib
import re


MIGRATIONS_DIR = pathlib.Path("packages/woobe-core/migrations/versions")
ENV_PATH = pathlib.Path("packages/woobe-core/migrations/env.py")
DB_BASE = pathlib.Path("packages/woobe-core/src/shared/infra/database/base.py")
AGENT_MODELS = pathlib.Path(
    "packages/woobe-core/src/modules/agent/infra/database/models.py"
)


class TestAlembicMigrationsSuccess:
    def test_alembic_env_imports_agent_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        assert "modules.agent.infra.database.models" in content

    def test_alembic_env_no_longer_imports_legacy_or_proprietary_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "from modules.ai.infra.models",
            "from modules.knowledge.infra.models",
            "from modules.runtime.infra.models",
            "from modules.tools.infra.database.models",
            "editions.cloud",
        ):
            assert forbidden not in content

    def test_alembic_env_imports_all_required_community_modules(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        required_imports = [
            "modules.identity.infra.database.models",
            "modules.core.infra.database.models",
            "modules.chat_surface.infra.database.models",
            "modules.metering.infra.database.models",
            "modules.observability.infra.database.models",
            "modules.agent.infra.database.models",
            "modules.network.infra.database.models",
        ]
        for module_path in required_imports:
            assert module_path in content, (
                f"packages/woobe-core/migrations/env.py must import {module_path}"
            )

    def test_migration_files_exist(self):
        assert list(MIGRATIONS_DIR.glob("*.py")), "Migration version files must exist"

    def test_migration_files_have_upgrade_and_downgrade(self):
        for version in MIGRATIONS_DIR.glob("*.py"):
            if version.name == "__init__.py":
                continue
            content = version.read_text(encoding="utf-8")
            assert "def upgrade" in content
            assert "def downgrade" in content


class TestAlembicMigrationsRejectsForbidden:
    def test_no_destructive_rename_in_migrations(self):
        for version in MIGRATIONS_DIR.glob("*.py"):
            if version.name == "__init__.py":
                continue
            assert "op.rename_table" not in version.read_text(encoding="utf-8")

    def test_no_new_cross_module_foreign_keys_in_recent_migrations(self):
        recent = sorted(MIGRATIONS_DIR.glob("*.py"), key=lambda path: path.stem)
        for version in recent[-6:]:
            if version.name == "__init__.py":
                continue
            content = version.read_text(encoding="utf-8")
            forbidden_fk_patterns = {
                "core.projects",
                "identity.workspaces",
                "identity.users",
                "billing.plans",
                "billing.subscriptions",
            }
            fk_matches = re.findall(r"ForeignKey\(['\"]([\w.]+)['\"]", content)
            for fk_target in fk_matches:
                assert fk_target not in forbidden_fk_patterns

    def test_no_on_delete_cascade_between_modules(self):
        for version in MIGRATIONS_DIR.glob("*.py"):
            if version.name == "__init__.py":
                continue
            content = version.read_text(encoding="utf-8")
            for match in re.finditer(r"ondelete\s*=\s*['\"]CASCADE['\"]", content):
                context_window = content[max(0, match.start() - 200) : match.end() + 50]
                has_external_module = re.search(
                    r"(core|identity|billing|metering|tools|observability)\.",
                    context_window,
                )
                assert not has_external_module, (
                    f"Migration {version.name}: ON DELETE CASCADE referencing external module"
                )

    def test_agent_migration_models_follow_expand_migrate_contract(self):
        assert AGENT_MODELS.is_file(), (
            "Agent models must exist under packages/woobe-core/src"
        )
        assert "__tablename__" in AGENT_MODELS.read_text(encoding="utf-8")


class TestAlembicMigrationsKeepsCompatibility:
    def test_database_base_exists(self):
        assert DB_BASE.is_file()
