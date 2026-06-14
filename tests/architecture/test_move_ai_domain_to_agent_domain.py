import ast
import warnings
from pathlib import Path

AGENT_DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent" / "domain"
AI_DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "ai" / "domain"

EXPECTED_ENTITIES = [
    "Agent",
    "AgentContract",
    "AgentModelConfig",
    "AgentPrompt",
    "AgentRelease",
    "AgentReleaseTest",
    "ProviderCredential",
]

EXPECTED_ENUMS = [
    "AgentStatus",
    "AgentType",
    "ContractStatus",
    "CredentialStatus",
    "KnowledgeVersionStatus",
    "ModelConfigStatus",
    "PromptStatus",
    "Provider",
    "ReleaseStatus",
    "ReleaseTestStatus",
    "SessionMode",
    "ValidationMode",
]

EXPECTED_ERRORS = [
    "AgentNotFoundError",
    "ContractNotFoundError",
    "CredentialNotFoundError",
    "ModelConfigNotFoundError",
    "PromptNotFoundError",
    "ReleaseNotFoundError",
    "ReleaseTestNotFoundError",
]

EXPECTED_REPOSITORIES = [
    "AgentContractRepository",
    "AgentModelConfigRepository",
    "AgentPromptRepository",
    "AgentReleaseRepository",
    "AgentReleaseTestRepository",
    "AgentRepository",
    "ProviderCredentialRepository",
]

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.ai",
    "modules.runtime",
    "modules.knowledge",
]


class TestMoveAiDomainToAgentDomain:
    def test_move_ai_domain_to_agent_domain_success(self):
        from modules.agent.domain.entities import (
            Agent,
            AgentContract,
            AgentModelConfig,
            AgentPrompt,
            AgentRelease,
            AgentReleaseTest,
            ProviderCredential,
        )

        for cls in [Agent, AgentContract, AgentModelConfig, AgentPrompt,
                    AgentRelease, AgentReleaseTest, ProviderCredential]:
            assert cls is not None
            instance = cls()
            assert instance is not None

        from modules.agent.domain.enums import (
            AgentStatus,
            AgentType,
            ContractStatus,
            CredentialStatus,
            KnowledgeVersionStatus,
            ModelConfigStatus,
            PromptStatus,
            Provider,
            ReleaseStatus,
            ReleaseTestStatus,
            SessionMode,
            ValidationMode,
        )

        for enum_cls in [AgentStatus, AgentType, ContractStatus, CredentialStatus,
                         KnowledgeVersionStatus, ModelConfigStatus, PromptStatus,
                         Provider, ReleaseStatus, ReleaseTestStatus, SessionMode,
                         ValidationMode]:
            assert len(enum_cls) > 0

        from modules.agent.domain.errors import (
            AgentNotFoundError,
            ContractNotFoundError,
            CredentialNotFoundError,
            ModelConfigNotFoundError,
            PromptNotFoundError,
            ReleaseNotFoundError,
            ReleaseTestNotFoundError,
        )

        for err_cls in [AgentNotFoundError, ContractNotFoundError,
                        CredentialNotFoundError, ModelConfigNotFoundError,
                        PromptNotFoundError, ReleaseNotFoundError,
                        ReleaseTestNotFoundError]:
            assert issubclass(err_cls, Exception)

        from modules.agent.domain.repositories import (
            AgentContractRepository,
            AgentModelConfigRepository,
            AgentPromptRepository,
            AgentReleaseRepository,
            AgentReleaseTestRepository,
            AgentRepository,
            ProviderCredentialRepository,
        )

        for repo_cls in [AgentContractRepository, AgentModelConfigRepository,
                         AgentPromptRepository, AgentReleaseRepository,
                         AgentReleaseTestRepository, AgentRepository,
                         ProviderCredentialRepository]:
            assert hasattr(repo_cls, "__abstractmethods__")

    def test_move_ai_domain_to_agent_domain_rejects_forbidden_dependency(self):
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

    def test_move_ai_domain_to_agent_domain_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.ai.domain import entities as ai_entities
            from modules.ai.domain import enums as ai_enums
            from modules.ai.domain import errors as ai_errors
            from modules.ai.domain import repositories as ai_repos

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from ai.domain shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        for entity_name in EXPECTED_ENTITIES:
            assert hasattr(ai_entities, entity_name), (
                f"Legacy shim ai.domain.entities missing: {entity_name}"
            )

        for enum_name in EXPECTED_ENUMS:
            assert hasattr(ai_enums, enum_name), (
                f"Legacy shim ai.domain.enums missing: {enum_name}"
            )

        for error_name in EXPECTED_ERRORS:
            assert hasattr(ai_errors, error_name), (
                f"Legacy shim ai.domain.errors missing: {error_name}"
            )

        for repo_name in EXPECTED_REPOSITORIES:
            assert hasattr(ai_repos, repo_name), (
                f"Legacy shim ai.domain.repositories missing: {repo_name}"
            )

        from modules.agent.domain import entities as agent_entities
        assert ai_entities.Agent is agent_entities.Agent, (
            "Shim must delegate to agent domain, not duplicate classes"
        )
