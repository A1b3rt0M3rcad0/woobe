from modules.agent.application import mcp_oauth
from modules.agent.application import mcp_oauth_flow_safety as mcp_oauth_flows
from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase
from modules.agent.application.mcp_permissions import (
    BulkUpdateMcpToolPermissionsUseCase,
    UpdateMcpToolPermissionsUseCase,
)
from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.application.mcp_tool_refresh import RefreshMcpProviderToolsUseCase
from modules.agent.application.project_environment_references import (
    ProjectEnvironmentToolUsageUseCase,
)
from modules.agent.application.runtime_tool_use_cases import (
    RuntimeExecuteToolUseCase,
    RuntimeTestToolUseCase,
)
from modules.agent.application.use_cases.tools_use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    GetToolUsageImpactUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)
from modules.agent.composition.resources import (
    DATABASE_ENGINE,
    PROJECT_ENVIRONMENT,
    SETTINGS,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAgentToolRepository,
    SQLAlchemyAgentToolSecretRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.tool_runtime_registry import build_tool_runtime_registry
from modules.agent.presentation.controllers.create_secret_controller import CreateSecretController
from modules.agent.presentation.controllers.create_tool_controller import CreateToolController
from modules.agent.presentation.controllers.delete_tool_controller import DeleteToolController
from modules.agent.presentation.controllers.discover_mcp_tools_controller import (
    DiscoverMcpToolsController,
)
from modules.agent.presentation.controllers.execute_tool_controller import ExecuteToolController
from modules.agent.presentation.controllers.get_tool_usage_impact_controller import (
    GetToolUsageImpactController,
)
from modules.agent.presentation.controllers.list_secrets_controller import ListSecretsController
from modules.agent.presentation.controllers.list_tools_by_agent_controller import (
    ListToolsByAgentController,
)
from modules.agent.presentation.controllers.list_tools_controller import ListToolsController
from modules.agent.presentation.controllers.mcp_connect_controllers import (
    CompleteMcpConnectController,
    DisconnectMcpConnectController,
    PollMcpDeviceConnectController,
    StartMcpConnectController,
    StartMcpDeviceConnectController,
    StatusMcpConnectController,
)
from modules.agent.presentation.controllers.mcp_permission_controllers import (
    BulkUpdateMcpPermissionsController,
    UpdateMcpPermissionsController,
)
from modules.agent.presentation.controllers.project_environment_tool_usage_controller import (
    ProjectEnvironmentToolUsageController,
)
from modules.agent.presentation.controllers.refresh_mcp_tools_controller import (
    RefreshMcpToolsController,
)
from modules.agent.presentation.controllers.test_tool_controller import TestToolController
from modules.agent.presentation.controllers.update_tool_controller import UpdateToolController
from modules.agent.presentation.controllers.update_tool_status_controller import (
    UpdateToolStatusController,
)
from shared.infra.transactional_handler import TransactionalHandler


def project_environment_tool_usage_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repo = SQLAlchemyAgentToolRepository(uow)
    use_case = ProjectEnvironmentToolUsageUseCase(repo)
    controller = ProjectEnvironmentToolUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_tool_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        mcp_bootstrapper = McpToolBootstrapper(
        get_http_tool_executor(),
        project_environment_resolver=PROJECT_ENVIRONMENT.resolve_values,
    )
    use_case = CreateToolUseCase(
        tool_repo,
        outbox,
        mcp_bootstrapper=mcp_bootstrapper,
        project_environment_key_validator=PROJECT_ENVIRONMENT.require_keys,
    )
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        use_case = UpdateToolUseCase(
        tool_repo,
        outbox,
        project_environment_key_validator=PROJECT_ENVIRONMENT.require_keys,
    )
    controller = UpdateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def delete_tool_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = DeleteToolUseCase(tool_repo, agent_repo, release_repo)
    controller = DeleteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_tool_usage_impact_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = GetToolUsageImpactUseCase(tool_repo, agent_repo, release_repo)
    controller = GetToolUsageImpactController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case = ListToolsUseCase(tool_repo)
    controller = ListToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_by_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case = ListToolsByAgentUseCase(tool_repo)
    controller = ListToolsByAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_status_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = UpdateToolStatusUseCase(tool_repo, outbox)
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)


def test_tool_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    registry = build_tool_runtime_registry(
        settings=SETTINGS,
        executor=get_http_tool_executor(),
    )
        use_case = RuntimeTestToolUseCase(
        runtime_registry=registry,
        project_environment_resolver=PROJECT_ENVIRONMENT.resolve_values,
    )
    controller = TestToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def discover_mcp_tools_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = DiscoverMcpToolsUseCase(get_http_tool_executor())
    controller = DiscoverMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def refresh_mcp_tools_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    tool_secret_repo = SQLAlchemyAgentToolSecretRepository(uow)
    runtime_executor = get_http_tool_executor()
    cipher = SecretCipherAdapter(SETTINGS.encryption_key)
    resolver = ToolSecretResolverAdapter(tool_secret_repo, cipher)
    auth_header_provider = mcp_oauth.McpOAuthConfigTokenProvider(
        executor=runtime_executor,
        cipher=cipher,
    )
        use_case = RefreshMcpProviderToolsUseCase(
        tool_repo=tool_repo,
        executor=runtime_executor,
        secret_resolver=resolver,
        auth_header_provider=auth_header_provider,
        project_environment_resolver=PROJECT_ENVIRONMENT.resolve_values,
    )
    controller = RefreshMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_mcp_tool_permissions_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case = UpdateMcpToolPermissionsUseCase(tool_repo)
    controller = UpdateMcpPermissionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def bulk_update_mcp_tool_permissions_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case = BulkUpdateMcpToolPermissionsUseCase(tool_repo)
    controller = BulkUpdateMcpPermissionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def start_mcp_oauth_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth_flows, "ProviderAwareMcpOAuthStartUseCase")
    use_case = use_case_cls(
        tool_repo=tool_repo,
        executor=get_http_tool_executor(),
        cipher=SecretCipherAdapter(SETTINGS.encryption_key),
    )
    controller = StartMcpConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def complete_mcp_oauth_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth, "McpOAuthCompleteUseCase")
    use_case = use_case_cls(
        tool_repo=tool_repo,
        executor=get_http_tool_executor(),
        cipher=SecretCipherAdapter(SETTINGS.encryption_key),
    )
    controller = CompleteMcpConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def start_mcp_oauth_device_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth_flows, "McpOAuthDeviceStartUseCase")
    use_case = use_case_cls(
        tool_repo=tool_repo,
        executor=get_http_tool_executor(),
        cipher=SecretCipherAdapter(SETTINGS.encryption_key),
    )
    controller = StartMcpDeviceConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def poll_mcp_oauth_device_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth_flows, "McpOAuthDevicePollUseCase")
    use_case = use_case_cls(
        tool_repo=tool_repo,
        executor=get_http_tool_executor(),
        cipher=SecretCipherAdapter(SETTINGS.encryption_key),
    )
    controller = PollMcpDeviceConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def status_mcp_oauth_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth, "McpOAuthStatusUseCase")
    controller = StatusMcpConnectController(use_case_cls(tool_repo=tool_repo))
    return TransactionalHandler(uow, controller.handle)


def disconnect_mcp_oauth_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    use_case_cls = getattr(mcp_oauth, "McpOAuthDisconnectUseCase")
    controller = DisconnectMcpConnectController(use_case_cls(tool_repo=tool_repo))
    return TransactionalHandler(uow, controller.handle)


def execute_tool_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    tool_secret_repo = SQLAlchemyAgentToolSecretRepository(uow)
    cipher = SecretCipherAdapter(SETTINGS.encryption_key)
    resolver = ToolSecretResolverAdapter(tool_secret_repo, cipher)
    registry = build_tool_runtime_registry(
        settings=SETTINGS,
        executor=get_http_tool_executor(),
        secret_resolver=resolver,
    )
    use_case = RuntimeExecuteToolUseCase(
        tool_repo=tool_repo,
        runtime_registry=registry,
    )
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_secret_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_secret_repo = SQLAlchemyAgentToolSecretRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    cipher = SecretCipherAdapter(SETTINGS.encryption_key)
    use_case = CreateSecretUseCase(tool_secret_repo, outbox, cipher)
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_secrets_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    tool_secret_repo = SQLAlchemyAgentToolSecretRepository(uow)
    use_case = ListSecretsUseCase(tool_secret_repo)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
