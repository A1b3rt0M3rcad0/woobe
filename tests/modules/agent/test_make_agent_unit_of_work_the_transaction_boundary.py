from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"
COMPOSERS_DIR = AGENT_DIR / "application" / "composers"
UOW_FILE = AGENT_DIR / "infra" / "database" / "unit_of_work.py"

AUOW_PROPERTIES = {
    "agents": "SQLAlchemyAgentRepository",
    "provider_credentials": "SQLAlchemyProviderCredentialRepository",
    "sessions": "SQLAlchemySessionRepository",
    "messages": "SQLAlchemyMessageRepository",
    "ask_jobs": "SQLAlchemyAskJobRepository",
    "document_collections": "SQLAlchemyDocumentCollectionRepository",
    "documents": "SQLAlchemyDocumentRepository",
    "document_chunks": "SQLAlchemyDocumentChunkRepository",
    "knowledge_versions": "SQLAlchemyKnowledgeVersionRepository",
}

# Composers that never used PostgresUnitOfWork (should be untouched)
NO_PGUOW_COMPOSERS = {"ask_agent_stream_composer.py", "get_ask_job_composer.py"}


def _get_py_files() -> list[Path]:
    return sorted(f for f in COMPOSERS_DIR.iterdir() if f.suffix == ".py" and not f.name.startswith("__"))


def _ast_parse(file_path: Path) -> ast.AST:
    source = file_path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(file_path))


class TestMakeAgentUnitOfWorkTransactionBoundary:
    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, f"{py_file.name} still imports PostgresUnitOfWork"

    def test_all_uow_composers_import_agent_unit_of_work(self):
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "from modules.agent.infra.database.unit_of_work import AgentUnitOfWork" in source, \
                f"{py_file.name} missing AgentUnitOfWork import"

    def test_all_uow_composers_instantiate_agent_unit_of_work(self):
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "AgentUnitOfWork(session_factory)" in source, \
                f"{py_file.name} does not instantiate AgentUnitOfWork"

    def test_get_ask_job_composer_unchanged(self):
        source = (COMPOSERS_DIR / "get_ask_job_composer.py").read_text(encoding="utf-8")
        assert "PostgresUnitOfWork" not in source
        assert "AgentUnitOfWork" not in source
        assert "SQLAlchemyAskJobRepository(session_factory)" in source

    def test_ask_agent_stream_composer_unchanged(self):
        source = (COMPOSERS_DIR / "ask_agent_stream_composer.py").read_text(encoding="utf-8")
        assert "PostgresUnitOfWork" not in source
        assert "AgentUnitOfWork" not in source
        assert "AskAgentStreamService(session_factory)" in source

    def test_agent_unit_of_work_coordinates_only_agent_repos_and_outbox_inbox(self):
        source = UOW_FILE.read_text(encoding="utf-8")
        assert "from modules.agent.infra.database.repositories" in source
        assert "SQLAlchemyAgentOutboxRepository" in source
        assert "SQLAlchemyAgentInboxRepository" in source
        for prop_name, repo_cls in AUOW_PROPERTIES.items():
            assert repo_cls in source, f"AgentUnitOfWork missing {repo_cls} for {prop_name} property"

    def test_agent_unit_of_work_has_no_cross_module_repos(self):
        source = UOW_FILE.read_text(encoding="utf-8")
        cross_module_patterns = ["modules.identity", "modules.core", "modules.billing",
                                 "modules.metering", "modules.observability", "modules.tools",
                                 "modules.ai", "modules.knowledge", "modules.runtime"]
        for pattern in cross_module_patterns:
            if f"from {pattern}" in source:
                pytest.fail(f"AgentUnitOfWork imports from {pattern}")

    def test_composers_use_uow_properties_for_matching_repos(self):
        composer_uow_properties_used = {
            "uow.agents", "uow.provider_credentials", "uow.sessions",
            "uow.messages", "uow.ask_jobs", "uow.document_collections",
            "uow.documents", "uow.document_chunks", "uow.knowledge_versions",
        }
        found = set()
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            source = py_file.read_text(encoding="utf-8")
            for prop in composer_uow_properties_used:
                if prop in source:
                    found.add(prop)
        missing = composer_uow_properties_used - found
        assert not missing, f"AUoW properties not used in any composer: {missing}"

    def test_outbox_writers_still_manually_instantiated(self):
        outbox_writers_found = 0
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            source = py_file.read_text(encoding="utf-8")
            for writer in ("SQLAlchemyOutboxEventWriter", "SQLAlchemyKnowledgeOutboxEventWriter",
                           "SQLAlchemyRuntimeOutboxEventWriter"):
                if f"{writer}(uow)" in source:
                    outbox_writers_found += 1
        assert outbox_writers_found >= 7, f"Expected 7+ outbox writer instantiations, found {outbox_writers_found}"

    def test_no_new_cross_module_imports_in_composers(self):
        cross_modules = {"modules.identity", "modules.core", "modules.billing",
                         "modules.metering", "modules.observability", "modules.tools"}
        pre_existing = {"modules.metering.infra.repositories", "modules.observability.infra.repositories",
                        "modules.tools.infra.repositories"}
        for py_file in _get_py_files():
            if py_file.name in NO_PGUOW_COMPOSERS:
                continue
            tree = _ast_parse(py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for cm in cross_modules:
                        if cm in node.module and node.module not in pre_existing:
                            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                            pytest.fail(f"{rel} imports from {node.module} (not in pre-existing allowlist)")

    def test_composers_count_matches_routes(self):
        comp_files = [f for f in _get_py_files() if f.name not in NO_PGUOW_COMPOSERS]
        assert len(comp_files) >= 40, f"Expected 40+ composer files with UoW, found {len(comp_files)}"
