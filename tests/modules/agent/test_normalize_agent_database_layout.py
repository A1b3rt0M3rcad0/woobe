from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_INFRA_DB = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database"

REQUIRED_DB_FILES = ["mappers.py", "models.py", "repositories.py", "unit_of_work.py", "__init__.py"]


class TestNormalizeAgentDatabaseLayout:
    def test_all_required_database_files_exist(self):
        for name in REQUIRED_DB_FILES:
            file_path = AGENT_INFRA_DB / name
            assert file_path.is_file(), f"Missing database file: {name}"

    def test_mappers_is_populated(self):
        mappers_file = AGENT_INFRA_DB / "mappers.py"
        assert mappers_file.stat().st_size > 10000, "mappers.py is too small"

    def test_models_is_populated(self):
        models_file = AGENT_INFRA_DB / "models.py"
        assert models_file.stat().st_size > 10000, "models.py is too small"

    def test_repositories_is_populated(self):
        repos_file = AGENT_INFRA_DB / "repositories.py"
        assert repos_file.stat().st_size > 10000, "repositories.py is too small"

    def test_unit_of_work_is_populated(self):
        uow_file = AGENT_INFRA_DB / "unit_of_work.py"
        assert uow_file.stat().st_size > 1000, "unit_of_work.py is too small"

    def test_mappers_import_from_domain_and_models(self):
        content = (AGENT_INFRA_DB / "mappers.py").read_text(encoding="utf-8")
        assert "from modules.agent.domain" in content, "mappers must import from domain"
        assert "from modules.agent.infra.database.models" in content, "mappers must import from models"

    def test_models_import_sqlalchemy(self):
        content = (AGENT_INFRA_DB / "models.py").read_text(encoding="utf-8")
        assert "from sqlalchemy" in content, "models must import sqlalchemy"

    def test_repositories_import_domain_and_models(self):
        content = (AGENT_INFRA_DB / "repositories.py").read_text(encoding="utf-8")
        assert "from modules.agent.domain" in content, "repositories must import from domain"
        assert "from modules.agent.infra.database.models" in content, "repositories must import models"

    def test_unit_of_work_owns_session_not_repositories(self):
        content = (AGENT_INFRA_DB / "unit_of_work.py").read_text(encoding="utf-8")
        assert "AsyncEngine" in content, "UoW must receive the process-wide engine"
        assert "async_sessionmaker" in content, "UoW must create its own session"
        assert "from modules.agent.infra.database.repositories" not in content
        assert "SQLAlchemyAgentOutboxRepository" not in content
        assert "SQLAlchemyAgentInboxRepository" not in content

    def test_database_session_facade_does_not_exist(self):
        assert not (AGENT_INFRA_DB / "database.py").exists(), (
            "database.py would expose a second session ownership path outside UnitOfWork"
        )
