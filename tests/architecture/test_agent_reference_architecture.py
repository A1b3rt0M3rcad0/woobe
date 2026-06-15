from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"
SPECS_DIR = PROJECT_ROOT / "specs" / "module-architecture-standardization"
INVENTORY_DIR = SPECS_DIR / "execution" / "inventory"

CANONICAL_LAYERS = {"application", "domain", "infra", "presentation"}

EXPECTED_CANONICAL_PATHS = [
    "application/composers",
    "application/dtos",
    "application/handlers",
    "application/use_cases",
    "domain/entities.py",
    "domain/enums.py",
    "domain/errors.py",
    "domain/events.py",
    "domain/repositories.py",
    "domain/services.py",
    "domain/value_objects.py",
    "infra/database/mappers.py",
    "infra/database/models.py",
    "infra/database/repositories.py",
    "infra/database/unit_of_work.py",
    "infra/messaging/consumers.py",
    "infra/messaging/event_mappers.py",
    "infra/messaging/publishers.py",
    "infra/workers/inbox_consumer.py",
    "infra/workers/inbox_processor.py",
    "infra/workers/outbox_dispatcher.py",
    "infra/workers/registry.py",
    "presentation/controllers",
    "presentation/mappers.py",
    "presentation/routes.py",
    "presentation/schemas.py",
]


class TestAgentReferenceArchitecture:
    def test_agent_has_all_canonical_layers(self):
        for layer in CANONICAL_LAYERS:
            layer_dir = AGENT_DIR / layer
            assert layer_dir.is_dir(), f"Missing layer: {layer}/"

    def test_agent_has_all_canonical_paths(self):
        for path in EXPECTED_CANONICAL_PATHS:
            full_path = AGENT_DIR / path
            exists = full_path.is_dir() or full_path.is_file()
            assert exists, f"Missing canonical path: {path}"

    def test_agent_all_packages_have_init_py(self):
        for dir_path in AGENT_DIR.rglob("*/"):
            if "__pycache__" in dir_path.parts:
                continue
            if not any(f.suffix == ".py" for f in dir_path.iterdir() if not f.name.startswith("__")):
                continue
            init_file = dir_path / "__init__.py"
            assert init_file.is_file(), f"Package without __init__.py: {dir_path.relative_to(PROJECT_ROOT).as_posix()}"

    def test_agent_has_routes_file(self):
        routes_file = AGENT_DIR / "presentation" / "routes.py"
        assert routes_file.exists()
        content = routes_file.read_text(encoding="utf-8")
        assert "APIRouter" in content
        assert "router" in content

    def test_agent_mappers_file_exists(self):
        mappers_file = AGENT_DIR / "presentation" / "mappers.py"
        assert mappers_file.exists()

    def test_agent_schemas_file_exists(self):
        schemas_file = AGENT_DIR / "presentation" / "schemas.py"
        assert schemas_file.exists()

    def test_agent_has_controllers_directory_with_multiple_files(self):
        controllers_dir = AGENT_DIR / "presentation" / "controllers"
        assert controllers_dir.is_dir()
        py_files = [f for f in controllers_dir.iterdir() if f.suffix == ".py" and not f.name.startswith("__")]
        assert len(py_files) >= 30, f"Expected 30+ controllers, found {len(py_files)}"

    def test_agent_inventory_documents_exist(self):
        required_inventories = [
            "files.md",
            "structure-matrix.md",
            "imports.md",
            "database-ownership.md",
            "routes.md",
            "transactions.md",
            "events.md",
            "workers.md",
        ]
        for name in required_inventories:
            inv_path = INVENTORY_DIR / name
            assert inv_path.exists(), f"Missing inventory: {name}"

    def test_agent_routes_reference_composers(self):
        routes_file = AGENT_DIR / "presentation" / "routes.py"
        content = routes_file.read_text(encoding="utf-8")
        composer_count = content.count("_composer(")
        assert composer_count >= 40, f"Expected 40+ composer references in routes, found {composer_count}"

    def test_agent_module_can_be_imported(self):
        init_file = AGENT_DIR / "__init__.py"
        assert init_file.exists()
        content = init_file.read_text(encoding="utf-8")
        assert "routes" in content
        assert "registry" in content

    def test_agent_has_no_direct_domain_to_infra_imports(self):
        domain_dir = AGENT_DIR / "domain"
        infra_dirs = {"database", "messaging", "workers", "llm"}
        import ast
        for py_file in domain_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for infra_dir in infra_dirs:
                        if f"infra.{infra_dir}" in node.module or f"/infra/{infra_dir}" in node.module:
                            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                            pytest.fail(f"Domain {rel} imports infra/{infra_dir}: {node.module}")

    def test_agent_domain_has_all_contract_files(self):
        domain_dir = AGENT_DIR / "domain"
        required = {"entities.py", "enums.py", "errors.py", "events.py", "repositories.py", "services.py", "value_objects.py"}
        existing = {f.name for f in domain_dir.iterdir() if f.suffix == ".py" and not f.name.startswith("__")}
        missing = required - existing
        assert not missing, f"Domain contract files missing: {missing}"

    def test_agent_domain_only_imports_self_or_shared(self):
        domain_dir = AGENT_DIR / "domain"
        import ast
        for py_file in domain_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    if mod.startswith("modules.") and not mod.startswith("modules.agent."):
                        rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                        pytest.fail(f"Domain file {rel} imports other module: {mod}")

    def test_agent_application_has_dtos_package_with_exports(self):
        dto_init = AGENT_DIR / "application" / "dtos" / "__init__.py"
        assert dto_init.exists()
        content = dto_init.read_text(encoding="utf-8")
        assert "__all__" in content

    def test_agent_application_has_use_cases_package_with_exports(self):
        uc_init = AGENT_DIR / "application" / "use_cases" / "__init__.py"
        assert uc_init.exists()
        content = uc_init.read_text(encoding="utf-8")
        assert "__all__" in content

    def test_agent_application_has_composers_and_handlers(self):
        assert (AGENT_DIR / "application" / "composers" / "__init__.py").exists()
        assert (AGENT_DIR / "application" / "handlers" / "__init__.py").exists()

    def test_agent_composers_import_use_cases_from_package(self):
        composers_dir = AGENT_DIR / "application" / "composers"
        count = 0
        for py_file in composers_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            if "from modules.agent.application.use_cases import" in content:
                count += 1
        assert count >= 40, f"Expected 40+ composers using use_cases package, found {count}"

    def test_agent_controllers_import_dtos_from_package(self):
        controllers_dir = AGENT_DIR / "presentation" / "controllers"
        count = 0
        for py_file in controllers_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text(encoding="utf-8")
            if "from modules.agent.application.dtos import" in content:
                count += 1
        assert count >= 25, f"Expected 25+ controllers using dtos package, found {count}"

    def test_agent_no_legacy_use_case_module_imports_in_composers(self):
        composers_dir = AGENT_DIR / "application" / "composers"
        legacy_uc = {".use_cases.ai_use_cases", ".use_cases.knowledge_use_cases", ".use_cases.runtime_use_cases"}
        for py_file in composers_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for pattern in legacy_uc:
                if pattern.replace(".", "") in content.replace(".", ""):
                    rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                    pytest.fail(f"Composer {rel} still uses legacy use case import: {pattern}")

    def test_agent_database_has_all_canonical_files(self):
        db_dir = AGENT_DIR / "infra" / "database"
        required = {"mappers.py", "models.py", "repositories.py", "unit_of_work.py"}
        existing = {f.name for f in db_dir.iterdir() if f.suffix == ".py" and not f.name.startswith("__")}
        missing = required - existing
        assert not missing, f"Database files missing: {missing}"

    def test_agent_unit_of_work_coordinates_agent_repos_and_outbox_inbox(self):
        uow_file = AGENT_DIR / "infra" / "database" / "unit_of_work.py"
        content = uow_file.read_text(encoding="utf-8")
        assert "outbox" in content.lower(), "UoW must have outbox property"
        assert "inbox" in content.lower(), "UoW must have inbox property"
        assert "SQLAlchemyAgentRepository" in content, "UoW must host agent repository"

    def test_all_composers_use_agent_unit_of_work(self):
        composers_dir = AGENT_DIR / "application" / "composers"
        skip = {"ask_agent_stream_composer.py", "get_ask_job_composer.py"}
        for py_file in composers_dir.glob("*.py"):
            if py_file.name.startswith("__") or py_file.name in skip:
                continue
            content = py_file.read_text(encoding="utf-8")
            assert "AgentUnitOfWork" in content, f"{py_file.name} must use AgentUnitOfWork"
            assert "PostgresUnitOfWork" not in content, f"{py_file.name} must not use PostgresUnitOfWork"

    def test_agent_unit_of_work_exposes_all_expected_lazy_properties(self):
        uow_file = AGENT_DIR / "infra" / "database" / "unit_of_work.py"
        content = uow_file.read_text(encoding="utf-8")
        expected_props = [
            "agents", "provider_credentials", "sessions", "messages",
            "ask_jobs", "document_collections", "documents", "document_chunks",
            "knowledge_versions", "outbox", "inbox",
        ]
        for prop in expected_props:
            assert f"def {prop}" in content, f"AgentUnitOfWork missing property: {prop}"

    def test_agent_unit_of_work_has_no_cross_module_references(self):
        uow_file = AGENT_DIR / "infra" / "database" / "unit_of_work.py"
        content = uow_file.read_text(encoding="utf-8")
        for mod in ("identity", "core", "billing", "metering", "observability", "tools"):
            assert f"modules.{mod}" not in content, f"AgentUnitOfWork references modules.{mod}"
