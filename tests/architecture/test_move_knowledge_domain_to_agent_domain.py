import ast
import warnings
from pathlib import Path

AGENT_DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent" / "domain"

EXPECTED_ENTITIES = [
    "DocumentCollection",
    "AgentCollection",
    "Document",
    "DocumentChunk",
    "KnowledgeVersion",
]

EXPECTED_ENUMS = [
    "CollectionStatus",
    "DocumentStatus",
    "ParserType",
    "KnowledgeVersionStatus",
]

EXPECTED_ERRORS = [
    "CollectionNotFoundError",
    "DocumentNotFoundError",
    "ChunkNotFoundError",
    "DuplicateCollectionError",
    "KnowledgeVersionNotFoundError",
]

EXPECTED_REPOSITORIES = [
    "DocumentCollectionRepository",
    "DocumentRepository",
    "AgentCollectionRepository",
    "DocumentChunkRepository",
    "KnowledgeVersionRepository",
]

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.knowledge",
    "modules.ai",
    "modules.runtime",
]


class TestMoveKnowledgeDomainToAgentDomain:
    def test_move_knowledge_domain_to_agent_domain_success(self):
        import modules.agent.domain.entities as agent_entities
        for name in EXPECTED_ENTITIES:
            assert hasattr(agent_entities, name), (
                f"Agent domain entities missing: {name}"
            )

        import modules.agent.domain.enums as agent_enums
        for name in EXPECTED_ENUMS:
            assert hasattr(agent_enums, name), (
                f"Agent domain enums missing: {name}"
            )

        import modules.agent.domain.errors as agent_errors
        for name in EXPECTED_ERRORS:
            assert hasattr(agent_errors, name), (
                f"Agent domain errors missing: {name}"
            )

        import modules.agent.domain.repositories as agent_repos
        for name in EXPECTED_REPOSITORIES:
            assert hasattr(agent_repos, name), (
                f"Agent domain repositories missing: {name}"
            )

    def test_move_knowledge_domain_to_agent_domain_rejects_forbidden_dependency(self):
        domain_files = [
            AGENT_DOMAIN_DIR / "entities.py",
            AGENT_DOMAIN_DIR / "enums.py",
            AGENT_DOMAIN_DIR / "errors.py",
            AGENT_DOMAIN_DIR / "repositories.py",
        ]

        for filepath in domain_files:
            assert filepath.exists(), f"Agent domain file missing: {filepath}"
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"Forbidden import '{node.module}' in {filepath.name}. "
                            f"Agent domain must not import from legacy modules."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES:
                            assert not alias.name.startswith(prefix), (
                                f"Forbidden import '{alias.name}' in {filepath.name}. "
                                f"Agent domain must not import from legacy modules."
                            )

    def test_move_knowledge_domain_to_agent_domain_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.knowledge.domain import entities as k_entities
            from modules.knowledge.domain import enums as k_enums
            from modules.knowledge.domain import errors as k_errors
            from modules.knowledge.domain import repositories as k_repos

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from knowledge.domain shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        for name in EXPECTED_ENTITIES:
            assert hasattr(k_entities, name), (
                f"Legacy shim knowledge.domain.entities missing: {name}"
            )

        for name in EXPECTED_ENUMS:
            assert hasattr(k_enums, name), (
                f"Legacy shim knowledge.domain.enums missing: {name}"
            )

        for name in EXPECTED_ERRORS:
            assert hasattr(k_errors, name), (
                f"Legacy shim knowledge.domain.errors missing: {name}"
            )

        for name in EXPECTED_REPOSITORIES:
            assert hasattr(k_repos, name), (
                f"Legacy shim knowledge.domain.repositories missing: {name}"
            )

        from modules.agent.domain.entities import DocumentCollection as AgentDocCollection
        assert k_entities.DocumentCollection is AgentDocCollection, (
            "Shim must delegate to agent domain, not duplicate classes"
        )
