import ast
import warnings
from pathlib import Path

AGENT_APP_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent" / "application"
AI_SERVICE_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "ai" / "service"
AI_COMPOSERS_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "ai" / "application" / "composers"

EXPECTED_USE_CASES = [
    "CreateAgentUseCase",
    "CreateContractUseCase",
    "CreateModelConfigUseCase",
    "CreatePromptUseCase",
    "CreateProviderCredentialUseCase",
    "CreateReleaseTestUseCase",
    "CreateReleaseUseCase",
    "DeleteReleaseUseCase",
    "GetAgentByIdUseCase",
    "GetContractUseCase",
    "GetModelConfigUseCase",
    "GetPromptUseCase",
    "GetReleaseTestUseCase",
    "GetReleaseUseCase",
    "ListAgentsUseCase",
    "ListContractsUseCase",
    "ListModelConfigsUseCase",
    "ListPromptsUseCase",
    "ListProviderCredentialsUseCase",
    "ListReleaseTestsUseCase",
    "ListReleasesUseCase",
    "PromoteReleaseUseCase",
    "RollbackReleaseUseCase",
    "UpdateAgentUseCase",
    "UpdateContractUseCase",
    "UpdateProviderCredentialUseCase",
]

EXPECTED_DTOS = [
    "CreateAgentInput",
    "CreateAgentOutput",
    "CreateContractInput",
    "CreateContractOutput",
    "CreateModelConfigInput",
    "CreateModelConfigOutput",
    "CreatePromptInput",
    "CreatePromptOutput",
    "CreateProviderCredentialInput",
    "CreateProviderCredentialOutput",
    "CreateReleaseInput",
    "CreateReleaseOutput",
    "CreateReleaseTestInput",
    "CreateReleaseTestOutput",
    "GetAgentInput",
    "ListAgentsInput",
    "ListAgentsOutput",
    "ListContractsOutput",
    "ListModelConfigsOutput",
    "ListPromptsOutput",
    "ListProviderCredentialsInput",
    "ListProviderCredentialsOutput",
    "ListReleaseTestsOutput",
    "ListReleasesOutput",
    "PromoteReleaseInput",
    "RollbackReleaseInput",
    "UpdateAgentInput",
    "UpdateAgentOutput",
    "UpdateContractInput",
    "UpdateContractOutput",
    "UpdateProviderCredentialInput",
    "UpdateProviderCredentialOutput",
]

EXPECTED_COMPOSERS = [
    "create_agent_composer",
    "create_contract_version_composer",
    "create_model_config_composer",
    "create_prompt_version_composer",
    "create_provider_credential_composer",
    "create_release_composer",
    "create_release_test_composer",
    "delete_release_composer",
    "get_agent_composer",
    "get_contract_version_composer",
    "get_model_config_composer",
    "get_prompt_version_composer",
    "get_release_composer",
    "list_agents_composer",
    "list_contract_versions_composer",
    "list_model_configs_composer",
    "list_prompt_versions_composer",
    "list_provider_credentials_composer",
    "list_release_tests_composer",
    "list_releases_composer",
    "promote_release_composer",
    "rollback_release_composer",
    "update_agent_composer",
    "update_contract_version_composer",
    "update_provider_credential_composer",
]

FORBIDDEN_IMPORT_PREFIXES_CORE = [
    "modules.ai.domain",
    "modules.ai.service",
]


class TestMoveAiApplicationToAgentApplication:
    def test_move_ai_application_to_agent_application_success(self):
        dtos_file = AGENT_APP_DIR / "dtos" / "ai_dtos.py"
        assert dtos_file.exists(), f"Agent DTOs file missing: {dtos_file}"

        use_cases_file = AGENT_APP_DIR / "use_cases" / "ai_use_cases.py"
        assert use_cases_file.exists(), f"Agent use cases file missing: {use_cases_file}"

        composers_dir = AGENT_APP_DIR / "composers"
        for composer_name in EXPECTED_COMPOSERS:
            composer_file = composers_dir / f"{composer_name}.py"
            assert composer_file.exists(), f"Agent composer missing: {composer_file}"

        import modules.agent.application.dtos.ai_dtos as agent_dtos
        for dto_name in EXPECTED_DTOS:
            assert hasattr(agent_dtos, dto_name), (
                f"Agent dtos missing class: {dto_name}"
            )

        import modules.agent.application.use_cases.ai_use_cases as agent_use_cases
        for uc_name in EXPECTED_USE_CASES:
            assert hasattr(agent_use_cases, uc_name), (
                f"Agent use_cases missing class: {uc_name}"
            )

    def test_move_ai_application_to_agent_application_rejects_forbidden_dependency(self):
        core_files = [
            AGENT_APP_DIR / "dtos" / "ai_dtos.py",
            AGENT_APP_DIR / "use_cases" / "ai_use_cases.py",
        ]

        for filepath in core_files:
            assert filepath.exists(), f"Agent application file missing: {filepath}"
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES_CORE:
                        assert not node.module.startswith(prefix), (
                            f"Forbidden import '{node.module}' in {filepath.name}. "
                            f"Agent application must not import from legacy ai domain/service."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES_CORE:
                            assert not alias.name.startswith(prefix), (
                                f"Forbidden import '{alias.name}' in {filepath.name}. "
                                f"Agent application must not import from legacy ai domain/service."
                            )

    def test_move_ai_application_to_agent_application_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.ai.service import dtos as ai_dtos
            from modules.ai.service import use_cases as ai_use_cases

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 2, (
            f"Expected at least 2 deprecation warnings from ai.service shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        for dto_name in EXPECTED_DTOS:
            assert hasattr(ai_dtos, dto_name), (
                f"Legacy shim ai.service.dtos missing: {dto_name}"
            )

        for uc_name in EXPECTED_USE_CASES:
            assert hasattr(ai_use_cases, uc_name), (
                f"Legacy shim ai.service.use_cases missing: {uc_name}"
            )

        from modules.agent.application.use_cases import ai_use_cases as agent_uc_module
        assert ai_use_cases.CreateAgentUseCase is agent_uc_module.CreateAgentUseCase, (
            "Shim must delegate to agent application, not duplicate classes"
        )
