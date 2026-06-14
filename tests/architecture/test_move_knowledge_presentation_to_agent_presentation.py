import ast
import importlib
import warnings
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "src"

EXPECTED_SCHEMAS = [
    "AgentCollectionResponse",
    "AttachCollectionRequest",
    "CreateCollectionRequest",
    "CollectionResponse",
    "UploadDocumentRequest",
    "DocumentResponse",
    "SearchRequest",
    "ChunkResponse",
    "CreateKnowledgeVersionRequest",
    "KnowledgeVersionResponse",
    "ListKnowledgeVersionsResponse",
]

EXPECTED_MAPPERS = [
    "collection_to_response",
    "create_collection_output_to_response",
    "agent_collection_output_to_response",
    "attach_collection_output_to_response",
    "document_to_response",
    "upload_document_output_to_response",
    "knowledge_version_to_response",
    "list_knowledge_versions_to_response",
    "chunk_output_to_response",
]

EXPECTED_CONTROLLERS = [
    "attach_collection_controller",
    "create_collection_controller",
    "create_knowledge_version_controller",
    "detach_collection_controller",
    "get_collection_controller",
    "get_document_controller",
    "list_agent_collections_controller",
    "list_collections_controller",
    "list_documents_controller",
    "list_knowledge_versions_controller",
    "search_chunks_controller",
    "upload_document_controller",
]

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.knowledge.domain",
    "modules.knowledge.service",
    "modules.knowledge.infra",
    "modules.knowledge.presentation",
]


class TestMoveKnowledgePresentationToAgentPresentation:

    def test_move_knowledge_presentation_to_agent_presentation_success(self):
        pres_dir = BASE / "modules" / "agent" / "presentation"
        schemas_path = pres_dir / "schemas.py"
        mappers_path = pres_dir / "mappers.py"
        routes_path = pres_dir / "routes.py"

        assert schemas_path.exists()
        assert mappers_path.exists()
        assert routes_path.exists()

        schemas_content = schemas_path.read_text(encoding="utf-8")
        for schema in EXPECTED_SCHEMAS:
            assert schema in schemas_content, f"Schema {schema} not found"

        mappers_content = mappers_path.read_text(encoding="utf-8")
        for mapper in EXPECTED_MAPPERS:
            assert mapper in mappers_content, f"Mapper {mapper} not found"

        routes_content = routes_path.read_text(encoding="utf-8")
        assert "knowledge_router" in routes_content

        controllers_dir = pres_dir / "controllers"
        for ctrl in EXPECTED_CONTROLLERS:
            assert (controllers_dir / f"{ctrl}.py").exists(), f"Missing controller {ctrl}"

    def test_move_knowledge_presentation_to_agent_presentation_rejects_forbidden_dependency(self):
        pres_dir = BASE / "modules" / "agent" / "presentation"
        for py_file in pres_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"{py_file.name} has forbidden import from {node.module}"
                        )

    def test_move_knowledge_presentation_to_agent_presentation_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            routes_mod = importlib.import_module("modules.knowledge.presentation.routes")
            schemas_mod = importlib.import_module("modules.knowledge.presentation.schemas")
            mappers_mod = importlib.import_module("modules.knowledge.presentation.mappers")

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 3

        assert hasattr(routes_mod, "router")
        assert hasattr(schemas_mod, "CollectionResponse")
        assert hasattr(mappers_mod, "collection_to_response")

        from modules.agent.presentation.mappers import collection_to_response
        assert mappers_mod.collection_to_response is collection_to_response
