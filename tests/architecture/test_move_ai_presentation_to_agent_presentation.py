import ast
import warnings
from pathlib import Path

AGENT_PRES_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent" / "presentation"

EXPECTED_SCHEMAS = [
    "CreateProviderCredentialRequest",
    "ProviderCredentialResponse",
    "UpdateProviderCredentialRequest",
    "CreateAgentRequest",
    "UpdateAgentRequest",
    "AgentResponse",
    "CreatePromptRequest",
    "PromptResponse",
    "ListPromptsResponse",
    "CreateContractRequest",
    "UpdateContractRequest",
    "ContractResponse",
    "ListContractsResponse",
    "CreateModelConfigRequest",
    "ModelConfigResponse",
    "ListModelConfigsResponse",
    "CreateReleaseRequest",
    "ReleaseResponse",
    "ListReleasesResponse",
    "PromoteReleaseRequest",
    "RollbackReleaseRequest",
    "CreateReleaseTestRequest",
    "ReleaseTestResponse",
    "ListReleaseTestsResponse",
]

EXPECTED_MAPPERS = [
    "credential_to_response",
    "agent_to_response",
    "prompt_to_response",
    "list_prompts_to_response",
    "contract_to_response",
    "list_contracts_to_response",
    "model_config_to_response",
    "list_model_configs_to_response",
    "release_to_response",
    "list_releases_to_response",
    "release_test_to_response",
    "list_release_tests_to_response",
]

EXPECTED_CONTROLLERS = [
    "create_agent_controller",
    "create_contract_version_controller",
    "create_model_config_controller",
    "create_prompt_version_controller",
    "create_provider_credential_controller",
    "create_release_controller",
    "create_release_test_controller",
    "delete_release_controller",
    "get_agent_controller",
    "get_contract_version_controller",
    "get_model_config_controller",
    "get_prompt_version_controller",
    "get_release_controller",
    "list_agents_controller",
    "list_contract_versions_controller",
    "list_model_configs_controller",
    "list_prompt_versions_controller",
    "list_provider_credentials_controller",
    "list_release_tests_controller",
    "list_releases_controller",
    "promote_release_controller",
    "rollback_release_controller",
    "update_agent_controller",
    "update_contract_version_controller",
    "update_provider_credential_controller",
]

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.ai",
    "modules.runtime",
    "modules.knowledge",
]


class TestMoveAiPresentationToAgentPresentation:
    def test_move_ai_presentation_to_agent_presentation_success(self):
        routes_file = AGENT_PRES_DIR / "routes.py"
        assert routes_file.exists(), f"Agent routes.py missing: {routes_file}"

        schemas_file = AGENT_PRES_DIR / "schemas.py"
        assert schemas_file.exists(), f"Agent schemas.py missing: {schemas_file}"

        mappers_file = AGENT_PRES_DIR / "mappers.py"
        assert mappers_file.exists(), f"Agent mappers.py missing: {mappers_file}"

        controllers_dir = AGENT_PRES_DIR / "controllers"
        assert controllers_dir.exists(), f"Agent controllers dir missing: {controllers_dir}"

        for ctrl_name in EXPECTED_CONTROLLERS:
            ctrl_file = controllers_dir / f"{ctrl_name}.py"
            assert ctrl_file.exists(), f"Agent controller missing: {ctrl_file}"

        import modules.agent.presentation.schemas as agent_schemas
        for schema_name in EXPECTED_SCHEMAS:
            assert hasattr(agent_schemas, schema_name), (
                f"Agent schemas missing class: {schema_name}"
            )

        import modules.agent.presentation.mappers as agent_mappers
        for mapper_name in EXPECTED_MAPPERS:
            assert hasattr(agent_mappers, mapper_name), (
                f"Agent mappers missing function: {mapper_name}"
            )

        from modules.agent.presentation.routes import router
        assert router is not None
        assert router.prefix == "/ai"

    def test_move_ai_presentation_to_agent_presentation_rejects_forbidden_dependency(self):
        core_files = [
            AGENT_PRES_DIR / "routes.py",
            AGENT_PRES_DIR / "schemas.py",
            AGENT_PRES_DIR / "mappers.py",
        ]
        controllers_dir = AGENT_PRES_DIR / "controllers"
        for ctrl_name in EXPECTED_CONTROLLERS:
            core_files.append(controllers_dir / f"{ctrl_name}.py")

        for filepath in core_files:
            assert filepath.exists(), f"Agent presentation file missing: {filepath}"
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"Forbidden import '{node.module}' in {filepath.name}. "
                            f"Agent presentation must not import from legacy modules."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES:
                            assert not alias.name.startswith(prefix), (
                                f"Forbidden import '{alias.name}' in {filepath.name}. "
                                f"Agent presentation must not import from legacy modules."
                            )

    def test_move_ai_presentation_to_agent_presentation_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.ai.presentation import routes as ai_routes
            from modules.ai.presentation import schemas as ai_schemas
            from modules.ai.presentation import mappers as ai_mappers

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 3, (
            f"Expected at least 3 deprecation warnings from ai.presentation shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        assert hasattr(ai_routes, "router"), (
            "Legacy shim ai.presentation.routes must export router"
        )

        from modules.agent.presentation.routes import router as agent_router
        assert ai_routes.router is agent_router, (
            "Shim must delegate to agent presentation, not duplicate router"
        )

        for schema_name in EXPECTED_SCHEMAS:
            assert hasattr(ai_schemas, schema_name), (
                f"Legacy shim ai.presentation.schemas missing: {schema_name}"
            )

        for mapper_name in EXPECTED_MAPPERS:
            assert hasattr(ai_mappers, mapper_name), (
                f"Legacy shim ai.presentation.mappers missing: {mapper_name}"
            )
