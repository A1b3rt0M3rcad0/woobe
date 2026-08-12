"""Architecture tests for Alembic/model import boundaries."""
import pathlib
import re


MIGRATIONS_DIR = pathlib.Path("migrations/versions")
ENV_PATH = pathlib.Path("migrations/env.py")
DB_BASE = pathlib.Path("src/shared/infra/database/base.py")


class TestAlembicMigrationsSuccess:
    def test_alembic_env_imports_agent_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        assert "modules.agent.infra.database.models" in content

    def test_alembic_env_no_longer_imports_legacy_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        for legacy in (
            "from modules.ai.infra.models",
            "from modules.knowledge.infra.models",
            "from modules.runtime.infra.models",
            "from modules.tools.infra.database.models",
        ):
            assert legacy not in content

    def test_alembic_env_imports_all_required_models(self):
        content = ENV_PATH.read_text(encoding="utf-8")
        required_imports = [
            "modules.identity.infra.database.models",
            "modules.core.infra.database.models",
            "modules.metering.infra.database.models",
            "editions.cloud.billing.infra.database.models",
            "modules.observability.infra.database.models",
            "modules.agent.infra.database.models",
        ]
        for module_path in required_imports:
            assert module_path in content, f"migrations/env.py must reference {module_path}"
        assert 'if os.environ.get("WOOBE_EDITION", "community").strip().lower() == "cloud"' in content

    def test_migration_files_exist(self):
        assert list(MIGRATIONS_DIR.glob("*.py"))

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
            if version.name != "__init__.py":
                assert "op.rename_table" not in version.read_text(encoding="utf-8")

    def test_no_new_cross_module_foreign_keys_in_recent_migrations(self):
        recent = sorted(MIGRATIONS_DIR.glob("*.py"), key=lambda p: p.stem)
        forbidden_fk_patterns = [
            "core.projects",
            "identity.organizations",
            "identity.users",
            "billing.plans",
            "billing.subscriptions",
        ]
        for version in recent[-6:]:
            if version.name == "__init__.py":
                continue
            content = version.read_text(encoding="utf-8")
            for fk_target in re.findall(r"ForeignKey\(['\"]([\w.]+)['\"]", content):
                assert fk_target not in forbidden_fk_patterns

    def test_no_on_delete_cascade_between_modules(self):
        for version in MIGRATIONS_DIR.glob("*.py"):
            if version.name == "__init__.py":
                continue
            content = version.read_text(encoding="utf-8")
            for match in re.finditer(r"ondelete\s*=\s*['\"]CASCADE['\"]", content):
                context_window = content[max(0, match.start() - 200): match.end() + 50]
                assert not re.search(
                    r"(core|identity|billing|metering|tools|observability)\.",
                    context_window,
                ), f"Migration {version.name}: cross-module ON DELETE CASCADE"

    def test_agent_migration_models_follow_expand_migrate_contract(self):
        agent_models = pathlib.Path("src/modules/agent/infra/database/models.py")
        if agent_models.is_file():
            assert "__tablename__" in agent_models.read_text(encoding="utf-8")


class TestAlembicMigrationsKeepsLegacyCompatibility:
    def test_database_base_exists(self):
        assert DB_BASE.is_file()
