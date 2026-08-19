from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application import mcp_oauth
from modules.agent.application import mcp_oauth_flow_safety as mcp_oauth_flows
from modules.agent.composition.composers.tool_runtime_factory import build_tool_runtime_registry
from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase
from modules.agent.application.mcp_permissions import (
    BulkUpdateMcpToolPermissionsUseCase,
    UpdateMcpToolPermissionsUseCase,
)
from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.application.mcp_tool_refresh import RefreshMcpProviderToolsUseCase
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
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_secret_controller import CreateSecretController
from modules.agent.presentation.controllers.create_tool_controller import CreateToolController
from modules.agent.presentation.controllers.delete_tool_controller import DeleteToolController
from modules.agent.presentation.controllers.discover_mcp_tools_controller import DiscoverMcpToolsController
from modules.agent.presentation.controllers.execute_tool_controller import ExecuteToolController
from modules.agent.presentation.controllers.get_tool_usage_impact_controller import GetToolUsageImpactController
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
from modules.agent.presentation.controllers.refresh_mcp_tools_controller import RefreshMcpToolsController
from modules.agent.presentation.controllers.test_tool_controller import TestToolController
from modules.agent.presentation.controllers.update_tool_controller import UpdateToolController
from modules.agent.presentation.controllers.update_tool_status_controller import (
    UpdateToolStatusController,
)
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.application.interfaces.outbox import OutboxEventWriter


def _agent_outbox(uow: AgentUnitOfWork) -> OutboxEventWriter:
    return cast(OutboxEventWriter, SQLAlchemyAgentOutboxEventWriter(uow))


def create_tool_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    mcp_bootstrapper = McpToolBootstrapper(executor or get_http_tool_executor())
    use_case = CreateToolUseCase(uow.tools, _agent_outbox(uow), mcp_bootstrapper=mcp_bootstrapper)
    controller = CreateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateToolUseCase(uow.tools, _agent_outbox(uow))
    controller = UpdateToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def delete_tool_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = DeleteToolUseCase(uow.tools, uow.agents, uow.releases)
    controller = DeleteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def get_tool_usage_impact_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = GetToolUsageImpactUseCase(uow.tools, uow.agents, uow.releases)
    controller = GetToolUsageImpactController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListToolsUseCase(uow.tools)
    controller = ListToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_tools_by_agent_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListToolsByAgentUseCase(uow.tools)
    controller = ListToolsByAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_tool_status_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateToolStatusUseCase(uow.tools, _agent_outbox(uow))
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)


def test_tool_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    registry = build_tool_runtime_registry(settings=settings, executor=executor or get_http_tool_executor())
    use_case = RuntimeTestToolUseCase(runtime_registry=registry)
    controller = TestToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def discover_mcp_tools_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = DiscoverMcpToolsUseCase(executor or get_http_tool_executor())
    controller = DiscoverMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def refresh_mcp_tools_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    runtime_executor = executor or get_http_tool_executor()
    cipher = SecretCipherAdapter(settings.encryption_key)
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    auth_header_provider = mcp_oauth.McpOAuthConfigTokenProvider(executor=runtime_executor, cipher=cipher)
    use_case = RefreshMcpProviderToolsUseCase(
        tool_repo=uow.tools,
        executor=runtime_executor,
        secret_resolver=resolver,
        auth_header_provider=auth_header_provider,
    )
    controller = RefreshMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def update_mcp_tool_permissions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateMcpToolPermissionsUseCase(uow.tools)
    controller = UpdateMcpPermissionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def bulk_update_mcp_tool_permissions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = BulkUpdateMcpToolPermissionsUseCase(uow.tools)
    controller = BulkUpdateMcpPermissionsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def start_mcp_oauth_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    use_case_cls = getattr(mcp_oauth_flows, "ProviderAwareMcpOAuthStartUseCase")
    use_case = use_case_cls(tool_repo=uow.tools, executor=executor or get_http_tool_executor(), cipher=SecretCipherAdapter(settings.encryption_key))
    controller = StartMcpConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def complete_mcp_oauth_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    use_case_cls = getattr(mcp_oauth, "McpOAuthCompleteUseCase")
    use_case = use_case_cls(tool_repo=uow.tools, executor=executor or get_http_tool_executor(), cipher=SecretCipherAdapter(settings.encryption_key))
    controller = CompleteMcpConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def start_mcp_oauth_device_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    use_case_cls = getattr(mcp_oauth_flows, "McpOAuthDeviceStartUseCase")
    use_case = use_case_cls(tool_repo=uow.tools, executor=executor or get_http_tool_executor(), cipher=SecretCipherAdapter(settings.encryption_key))
    controller = StartMcpDeviceConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def poll_mcp_oauth_device_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    use_case_cls = getattr(mcp_oauth_flows, "McpOAuthDevicePollUseCase")
    use_case = use_case_cls(tool_repo=uow.tools, executor=executor or get_http_tool_executor(), cipher=SecretCipherAdapter(settings.encryption_key))
    controller = PollMcpDeviceConnectController(use_case)
    return TransactionalHandler(uow, controller.handle)


def status_mcp_oauth_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case_cls = getattr(mcp_oauth, "McpOAuthStatusUseCase")
    controller = StatusMcpConnectController(use_case_cls(tool_repo=uow.tools))
    return TransactionalHandler(uow, controller.handle)


def disconnect_mcp_oauth_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case_cls = getattr(mcp_oauth, "McpOAuthDisconnectUseCase")
    controller = DisconnectMcpConnectController(use_case_cls(tool_repo=uow.tools))
    return TransactionalHandler(uow, controller.handle)


def execute_tool_composer(session_factory: async_sessionmaker[AsyncSession], executor: HttpToolExecutor | None = None) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    registry = build_tool_runtime_registry(settings=settings, executor=executor or get_http_tool_executor(), secret_resolver=resolver)
    use_case = RuntimeExecuteToolUseCase(tool_repo=uow.tools, runtime_registry=registry)
    controller = ExecuteToolController(use_case)
    return TransactionalHandler(uow, controller.handle)


def create_secret_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    use_case = CreateSecretUseCase(uow.tool_secrets, _agent_outbox(uow), cipher)
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_secrets_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListSecretsUseCase(uow.tool_secrets)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
