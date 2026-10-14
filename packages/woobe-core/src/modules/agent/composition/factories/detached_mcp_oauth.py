"""Existing OAuth protocols composed with request-local, detached worksets."""
from modules.agent.application import mcp_oauth
from modules.agent.application import mcp_oauth_flow_safety
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.oauth_protocol_executor import OAuthProtocolExecutor
from modules.agent.infra.handlers.detached_mcp_oauth import DetachedMcpOAuthOperation
from modules.agent.presentation.controllers.mcp_connect_controllers import (
    StartMcpConnectController, CompleteMcpConnectController,
    StartMcpDeviceConnectController, PollMcpDeviceConnectController,
)


def _operation(use_case_cls, controller_cls):
    def controller(repository):
        use_case = use_case_cls(tool_repo=repository, executor=OAuthProtocolExecutor(get_http_tool_executor()),
            cipher=SecretCipherAdapter(SETTINGS.encryption_key))
        return controller_cls(use_case)
    return DetachedMcpOAuthOperation(build_agent_uow, controller)


def build_mcp_oauth_start():
    return _operation(getattr(mcp_oauth_flow_safety, 'ProviderAwareMcpOAuthStartUseCase'), StartMcpConnectController)


def build_mcp_oauth_complete():
    return _operation(getattr(mcp_oauth, 'McpOAuthCompleteUseCase'), CompleteMcpConnectController)


def build_mcp_oauth_device_start():
    return _operation(getattr(mcp_oauth_flow_safety, 'McpOAuthDeviceStartUseCase'), StartMcpDeviceConnectController)


def build_mcp_oauth_device_poll():
    return _operation(getattr(mcp_oauth_flow_safety, 'McpOAuthDevicePollUseCase'), PollMcpDeviceConnectController)
