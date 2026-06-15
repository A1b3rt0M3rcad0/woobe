from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"

CANONICAL_LAYERS = ["application", "domain", "infra", "presentation"]

REQUIRED_TOP_LEVEL_FILES = ["__init__.py"]

EXPECTED_DOMAIN_FILES = [
    "entities.py", "enums.py", "errors.py", "events.py",
    "repositories.py", "services.py", "value_objects.py",
]

EXPECTED_APPLICATION_SUBDIRS = ["composers", "dtos", "handlers", "use_cases"]

EXPECTED_INFRA_SUBDIRS = ["database", "messaging", "workers", "llm"]

EXPECTED_DATABASE_FILES = ["__init__.py", "mappers.py", "models.py", "repositories.py", "unit_of_work.py"]

EXPECTED_MESSAGING_FILES = ["__init__.py", "consumers.py", "event_mappers.py", "inbox_handlers.py", "publishers.py"]

EXPECTED_WORKER_FILES = ["__init__.py", "inbox_consumer.py", "inbox_processor.py", "outbox_dispatcher.py", "registry.py"]

EXPECTED_PRESENTATION_FILES = ["__init__.py", "mappers.py", "routes.py", "schemas.py"]

FORBIDDEN_IMPORTS_IN_DOMAIN = ["sqlalchemy", "fastapi", "aio_pika"]


class TestLockAgentReferenceArchitecture:
    # --- Layer structure tests ---

    def test_agent_has_all_canonical_layers(self):
        for layer in CANONICAL_LAYERS:
            layer_dir = AGENT_DIR / layer
            assert layer_dir.is_dir(), f"Missing layer directory: {layer}/"

    def test_agent_has_top_level_init(self):
        init_file = AGENT_DIR / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text(encoding="utf-8")
        assert "routes" in content
        assert "registry" in content
        assert "__all__" in content

    # --- Domain layer tests ---

    def test_domain_has_all_required_files(self):
        domain_dir = AGENT_DIR / "domain"
        for name in EXPECTED_DOMAIN_FILES:
            file_path = domain_dir / name
            assert file_path.is_file(), f"Missing domain file: {name}"

    def test_domain_does_not_import_infrastructure(self):
        domain_dir = AGENT_DIR / "domain"
        for py_file in domain_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            for imp in FORBIDDEN_IMPORTS_IN_DOMAIN:
                if f"import {imp}" in content or f"from {imp}" in content:
                    rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                    pytest.fail(f"Domain file {rel} imports {imp}")

    def test_domain_does_not_import_other_modules(self):
        domain_dir = AGENT_DIR / "domain"
        for py_file in domain_dir.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            if "from modules." in content and "from modules.agent." not in content:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                pytest.fail(f"Domain file {rel} imports other module")

    # --- Application layer tests ---

    def test_application_has_all_required_subdirs(self):
        app_dir = AGENT_DIR / "application"
        for name in EXPECTED_APPLICATION_SUBDIRS:
            subdir = app_dir / name
            assert subdir.is_dir(), f"Missing application subdir: {name}"

    def test_application_dtos_has_init_with_exports(self):
        content = (AGENT_DIR / "application" / "dtos" / "__init__.py").read_text(encoding="utf-8")
        assert "__all__" in content

    def test_application_use_cases_has_init_with_exports(self):
        content = (AGENT_DIR / "application" / "use_cases" / "__init__.py").read_text(encoding="utf-8")
        assert "__all__" in content

    def test_application_handlers_has_init(self):
        assert (AGENT_DIR / "application" / "handlers" / "__init__.py").is_file()

    # --- Infrastructure layer tests ---

    def test_infra_has_all_required_subdirs(self):
        infra_dir = AGENT_DIR / "infra"
        for name in EXPECTED_INFRA_SUBDIRS:
            subdir = infra_dir / name
            assert subdir.is_dir(), f"Missing infra subdir: {name}"

    def test_database_has_all_required_files(self):
        db_dir = AGENT_DIR / "infra" / "database"
        for name in EXPECTED_DATABASE_FILES:
            file_path = db_dir / name
            assert file_path.is_file(), f"Missing database file: {name}"

    def test_messaging_has_all_required_files(self):
        msg_dir = AGENT_DIR / "infra" / "messaging"
        for name in EXPECTED_MESSAGING_FILES:
            file_path = msg_dir / name
            assert file_path.is_file(), f"Missing messaging file: {name}"

    def test_workers_has_all_required_files(self):
        workers_dir = AGENT_DIR / "infra" / "workers"
        for name in EXPECTED_WORKER_FILES:
            file_path = workers_dir / name
            assert file_path.is_file(), f"Missing worker file: {name}"

    def test_unit_of_work_coordinates_agent_repos_only(self):
        uow_content = (AGENT_DIR / "infra" / "database" / "unit_of_work.py").read_text(encoding="utf-8")
        expected_repos = [
            "SQLAlchemyAgentRepository",
            "SQLAlchemyProviderCredentialRepository",
            "SQLAlchemySessionRepository",
            "SQLAlchemyMessageRepository",
            "SQLAlchemyAskJobRepository",
            "SQLAlchemyDocumentCollectionRepository",
            "SQLAlchemyDocumentRepository",
            "SQLAlchemyDocumentChunkRepository",
            "SQLAlchemyKnowledgeVersionRepository",
            "SQLAlchemyAgentOutboxRepository",
            "SQLAlchemyAgentInboxRepository",
        ]
        for repo in expected_repos:
            assert repo in uow_content, f"AgentUnitOfWork missing {repo}"
        for mod in ("identity", "core", "billing", "metering", "observability", "tools"):
            assert f"modules.{mod}" not in uow_content, f"AgentUnitOfWork references {mod}"

    # --- Presentation layer tests ---

    def test_presentation_has_all_required_files(self):
        pres_dir = AGENT_DIR / "presentation"
        for name in EXPECTED_PRESENTATION_FILES:
            file_path = pres_dir / name
            assert file_path.is_file(), f"Missing presentation file: {name}"

    def test_routes_reference_40_plus_composers(self):
        content = (AGENT_DIR / "presentation" / "routes.py").read_text(encoding="utf-8")
        composer_count = content.count("_composer(")
        assert composer_count >= 40, f"Expected 40+ composer references, found {composer_count}"

    def test_controllers_directory_has_30_plus_files(self):
        controllers_dir = AGENT_DIR / "presentation" / "controllers"
        py_files = [f for f in controllers_dir.iterdir() if f.suffix == ".py" and not f.name.startswith("__")]
        assert len(py_files) >= 30, f"Expected 30+ controllers, found {len(py_files)}"

    # --- No legacy tests ---

    def test_no_legacy_imports_anywhere_in_agent(self):
        legacy_patterns = ["modules.ai", "modules.knowledge", "modules.runtime"]
        for py_file in AGENT_DIR.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            for pattern in legacy_patterns:
                if pattern in content:
                    rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                    pytest.fail(f"{rel} contains legacy reference: {pattern}")

    # --- Aggregate structure counts ---

    def test_agent_has_100_plus_python_files(self):
        py_files = [f for f in AGENT_DIR.rglob("*.py") if "__pycache__" not in f.parts]
        assert len(py_files) >= 100, f"Expected 100+ Python files in agent, found {len(py_files)}"

    def test_all_files_in_canonical_directories(self):
        for py_file in AGENT_DIR.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(AGENT_DIR).as_posix()
            top_dir = rel.split("/")[0]
            if top_dir == "__init__.py":
                continue
            assert top_dir in CANONICAL_LAYERS, f"File {rel} not in a canonical layer"
