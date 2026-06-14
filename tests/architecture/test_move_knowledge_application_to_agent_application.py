import ast
import importlib
import warnings
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[2] / "src"

EXPECTED_DTOS = [
    "CreateCollectionInput",
    "CreateCollectionOutput",
    "AttachCollectionInput",
    "AttachCollectionOutput",
    "AgentCollectionOutput",
    "UploadDocumentInput",
    "UploadDocumentOutput",
    "DocumentChunkOutput",
    "SearchChunksInput",
    "SearchChunksOutput",
    "ListCollectionsInput",
    "GetCollectionInput",
    "ListDocumentsInput",
    "GetDocumentInput",
    "CreateKnowledgeVersionInput",
    "CreateKnowledgeVersionOutput",
    "ListKnowledgeVersionsOutput",
]

EXPECTED_USE_CASES = [
    "ListAgentCollectionsUseCase",
    "AttachCollectionUseCase",
    "DetachCollectionUseCase",
    "CreateCollectionUseCase",
    "UploadDocumentUseCase",
    "SearchChunksUseCase",
    "ListCollectionsUseCase",
    "GetCollectionUseCase",
    "ListDocumentsUseCase",
    "GetDocumentUseCase",
    "CreateKnowledgeVersionUseCase",
    "ListKnowledgeVersionsUseCase",
]

EXPECTED_COMPOSERS = [
    "attach_collection_composer",
    "create_collection_composer",
    "create_knowledge_version_composer",
    "detach_collection_composer",
    "get_collection_composer",
    "get_document_composer",
    "list_agent_collections_composer",
    "list_collections_composer",
    "list_documents_composer",
    "list_knowledge_versions_composer",
    "search_chunks_composer",
    "upload_document_composer",
]

FORBIDDEN_IMPORT_PREFIXES_CORE = [
    "modules.knowledge.domain",
    "modules.knowledge.service",
]


class TestMoveKnowledgeApplicationToAgentApplication:

    def test_move_knowledge_application_to_agent_application_success(self):
        dtos_path = BASE / "modules" / "agent" / "application" / "dtos" / "knowledge_dtos.py"
        use_cases_path = BASE / "modules" / "agent" / "application" / "use_cases" / "knowledge_use_cases.py"

        assert dtos_path.exists(), f"Missing {dtos_path}"
        assert use_cases_path.exists(), f"Missing {use_cases_path}"

        dtos_content = dtos_path.read_text(encoding="utf-8")
        for dto in EXPECTED_DTOS:
            assert dto in dtos_content, f"DTO {dto} not found in knowledge_dtos.py"

        use_cases_content = use_cases_path.read_text(encoding="utf-8")
        for uc in EXPECTED_USE_CASES:
            assert uc in use_cases_content, f"UseCase {uc} not found in knowledge_use_cases.py"

        composers_dir = BASE / "modules" / "agent" / "application" / "composers"
        for composer_name in EXPECTED_COMPOSERS:
            composer_file = composers_dir / f"{composer_name}.py"
            assert composer_file.exists(), f"Missing composer {composer_file}"

    def test_move_knowledge_application_to_agent_application_rejects_forbidden_dependency(self):
        dtos_path = BASE / "modules" / "agent" / "application" / "dtos" / "knowledge_dtos.py"
        use_cases_path = BASE / "modules" / "agent" / "application" / "use_cases" / "knowledge_use_cases.py"

        for path in [dtos_path, use_cases_path]:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES_CORE:
                        assert not node.module.startswith(prefix), (
                            f"{path.name} has forbidden top-level import from {node.module}"
                        )

    def test_move_knowledge_application_to_agent_application_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dtos_mod = importlib.import_module("modules.knowledge.service.dtos")
            uc_mod = importlib.import_module("modules.knowledge.service.use_cases")

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 2, (
            f"Expected at least 2 DeprecationWarnings, got {len(deprecation_warnings)}"
        )

        for dto in EXPECTED_DTOS:
            assert hasattr(dtos_mod, dto), f"Legacy shim missing DTO {dto}"

        for uc in EXPECTED_USE_CASES:
            assert hasattr(uc_mod, uc), f"Legacy shim missing UseCase {uc}"

        from modules.agent.application.use_cases.knowledge_use_cases import CreateCollectionUseCase
        assert uc_mod.CreateCollectionUseCase is CreateCollectionUseCase, (
            "Legacy shim must delegate to agent module, not duplicate"
        )
