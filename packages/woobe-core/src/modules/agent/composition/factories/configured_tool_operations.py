"""Detached Tool operations; legacy UoWs are created only if that path is used."""
from modules.agent.application import mcp_oauth
from modules.agent.application.mcp_tool_refresh import RefreshMcpProviderToolsUseCase
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.composition.factories.configuration_tool_preparation import build_configuration_tool_preparation
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.runtime_secret_resolver import RuntimeToolSecretResolver
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.oauth_protocol_executor import OAuthProtocolExecutor
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.project_environment_reader import SQLAlchemyProjectEnvironmentReader
from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository, SQLAlchemyAgentToolSecretRepository
from modules.agent.infra.execution.tool_runtime_registry import build_tool_runtime_registry
from modules.agent.infra.handlers.configured_tool_operation import ConfiguredToolOperation
from modules.agent.presentation.controllers.execute_tool_controller import ExecuteToolController
from modules.agent.presentation.controllers.refresh_mcp_tools_controller import RefreshMcpToolsController
from shared.infra.transactional_handler import TransactionalHandler


def _legacy_execute():
    uow = build_agent_uow()
    resolver = ToolSecretResolverAdapter(SQLAlchemyAgentToolSecretRepository(uow), SecretCipherAdapter(SETTINGS.encryption_key))
    registry = build_tool_runtime_registry(settings=SETTINGS, executor=get_http_tool_executor(), secret_resolver=resolver)
    controller = ExecuteToolController(RuntimeExecuteToolUseCase(SQLAlchemyAgentToolRepository(uow), registry))
    return TransactionalHandler(uow, controller.handle)


def _legacy_refresh():
    uow = build_agent_uow()
    executor = get_http_tool_executor()
    cipher = SecretCipherAdapter(SETTINGS.encryption_key)
    use_case = RefreshMcpProviderToolsUseCase(
        tool_repo=SQLAlchemyAgentToolRepository(uow), executor=executor,
        secret_resolver=ToolSecretResolverAdapter(SQLAlchemyAgentToolSecretRepository(uow), cipher),
        auth_header_provider=mcp_oauth.McpOAuthConfigTokenProvider(executor=OAuthProtocolExecutor(executor), cipher=cipher),
        project_environment_resolver=SQLAlchemyProjectEnvironmentReader(uow, encryption_key=SETTINGS.encryption_key).resolve_values,
    )
    return TransactionalHandler(uow, RefreshMcpToolsController(use_case).handle)


def build_configured_tool_execution():
    registry = build_tool_runtime_registry(settings=SETTINGS, executor=get_http_tool_executor(),
        secret_resolver=RuntimeToolSecretResolver())
    return ConfiguredToolOperation(build_agent_uow, _legacy_execute, registry=registry)


def build_configured_tool_refresh():
    return ConfiguredToolOperation(build_agent_uow, _legacy_refresh, preparation=build_configuration_tool_preparation())
