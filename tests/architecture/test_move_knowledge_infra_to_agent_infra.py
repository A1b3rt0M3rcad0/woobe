import ast
import importlib
import warnings
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[2] / "src"

EXPECTED_MODELS = [
    "DocumentCollectionModel",
    "AgentCollectionModel",
    "DocumentModel",
    "DocumentChunkModel",
    "KnowledgeVersionModel",
    "KnowledgeOutboxEventModel",
    "KnowledgeInboxEventModel",
]

EXPECTED_MAPPERS = [
    "agent_collection_to_model",
    "agent_collection_model_to_entity",
    "collection_to_model",
    "model_to_collection",
    "document_to_model",
    "model_to_document",
    "chunk_to_model",
    "model_to_chunk",
    "knowledge_version_to_model",
    "knowledge_version_model_to_entity",
]

EXPECTED_REPOSITORIES = [
    "SQLAlchemyAgentCollectionRepository",
    "SQLAlchemyDocumentCollectionRepository",
    "SQLAlchemyDocumentRepository",
    "SQLAlchemyDocumentChunkRepository",
    "SQLAlchemyKnowledgeVersionRepository",
    "SQLAlchemyKnowledgeOutboxEventWriter",
]

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.knowledge.domain",
    "modules.knowledge.service",
    "modules.knowledge.infra",
]


class TestMoveKnowledgeInfraToAgentInfra:

    def test_move_knowledge_infra_to_agent_infra_success(self):
        db_dir = BASE / "modules" / "agent" / "infra" / "database"
        models_path = db_dir / "models.py"
        mappers_path = db_dir / "mappers.py"
        repos_path = db_dir / "repositories.py"

        assert models_path.exists(), f"Missing {models_path}"
        assert mappers_path.exists(), f"Missing {mappers_path}"
        assert repos_path.exists(), f"Missing {repos_path}"

        models_content = models_path.read_text(encoding="utf-8")
        for model in EXPECTED_MODELS:
            assert model in models_content, f"Model {model} not found in models.py"

        mappers_content = mappers_path.read_text(encoding="utf-8")
        for mapper in EXPECTED_MAPPERS:
            assert mapper in mappers_content, f"Mapper {mapper} not found in mappers.py"

        repos_content = repos_path.read_text(encoding="utf-8")
        for repo in EXPECTED_REPOSITORIES:
            assert repo in repos_content, f"Repository {repo} not found in repositories.py"

    def test_move_knowledge_infra_to_agent_infra_rejects_forbidden_dependency(self):
        db_dir = BASE / "modules" / "agent" / "infra" / "database"
        for py_file in db_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"{py_file.name} has forbidden top-level import from {node.module}"
                        )

    def test_move_knowledge_infra_to_agent_infra_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            models_mod = importlib.import_module("modules.knowledge.infra.models")
            mappers_mod = importlib.import_module("modules.knowledge.infra.mappers")
            repos_mod = importlib.import_module("modules.knowledge.infra.repositories")

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 3, (
            f"Expected at least 3 DeprecationWarnings, got {len(deprecation_warnings)}"
        )

        assert hasattr(models_mod, "DocumentCollectionModel")
        assert hasattr(models_mod, "DocumentModel")
        assert hasattr(models_mod, "DocumentChunkModel")

        assert hasattr(mappers_mod, "model_to_document")
        assert hasattr(mappers_mod, "model_to_collection")

        assert hasattr(repos_mod, "SQLAlchemyDocumentCollectionRepository")
        assert hasattr(repos_mod, "SQLAlchemyOutboxEventWriter")

        from modules.agent.infra.database.repositories import SQLAlchemyDocumentCollectionRepository
        assert repos_mod.SQLAlchemyDocumentCollectionRepository is SQLAlchemyDocumentCollectionRepository
