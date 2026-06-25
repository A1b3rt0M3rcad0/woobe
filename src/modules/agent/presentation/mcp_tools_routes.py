from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.application.composers.tools_composers import (
    complete_mcp_oauth_composer,
    disconnect_mcp_oauth_composer,
    discover_mcp_tools_composer,
    poll_mcp_oauth_device_composer,
    start_mcp_oauth_composer,
    start_mcp_oauth_device_composer,
    status_mcp_oauth_composer,
)
from modules.agent.application.mcp_oauth import McpOAuthConfigTokenProvider
from modules.agent.application.mcp_permissions import (
    BulkUpdateMcpToolPermissionsUseCase,
    UpdateMcpToolPermissionsUseCase,
)
from modules.agent.application.mcp_tool_refresh import RefreshMcpProviderToolsUseCase
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.mcp_permission_controllers import (
    BulkUpdateMcpPermissionsController,
    UpdateMcpPermissionsController,
)
from modules.agent.presentation.controllers.refresh_mcp_tools_controller import RefreshMcpToolsController
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/tools", tags=["tools"])


def _update_permissions_handler(session_factory):
    uow = AgentUnitOfWork(session_factory)
    controller = UpdateMcpPermissionsController(UpdateMcpToolPermissionsUseCase(uow.tools))
    return TransactionalHandler(uow, controller.handle)


def _bulk_permissions_handler(session_factory):
    uow = AgentUnitOfWork(session_factory)
    controller = BulkUpdateMcpPermissionsController(BulkUpdateMcpToolPermissionsUseCase(uow.tools))
    return TransactionalHandler(uow, controller.handle)


def _refresh_handler(session_factory):
    uow = AgentUnitOfWork(session_factory)
    settings = Settings.model_validate({})
    cipher = SecretCipherAdapter(settings.encryption_key)
    executor = get_http_tool_executor()
    resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
    provider = McpOAuthConfigTokenProvider(executor=executor, cipher=cipher)
    use_case = RefreshMcpProviderToolsUseCase(tool_repo=uow.tools, executor=executor, secret_resolver=resolver, auth_header_provider=provider)
    controller = RefreshMcpToolsController(use_case)
    return TransactionalHandler(uow, controller.handle)


@router.post("/mcp/discover")
async def discover_mcp_tools(request: FastAPIRequest):
    handler = discover_mcp_tools_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/refresh")
async def refresh_mcp_tools(request: FastAPIRequest):
    handler = _refresh_handler(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/mcp/permissions")
async def update_mcp_permissions(request: FastAPIRequest):
    handler = _update_permissions_handler(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/permissions/bulk")
async def bulk_update_mcp_permissions(request: FastAPIRequest):
    handler = _bulk_permissions_handler(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/start")
async def start_mcp_oauth(request: FastAPIRequest):
    handler = start_mcp_oauth_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/complete")
async def complete_mcp_oauth(request: FastAPIRequest):
    handler = complete_mcp_oauth_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/start")
async def start_mcp_oauth_device(request: FastAPIRequest):
    handler = start_mcp_oauth_device_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/poll")
async def poll_mcp_oauth_device(request: FastAPIRequest):
    handler = poll_mcp_oauth_device_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/status")
async def status_mcp_oauth(request: FastAPIRequest):
    handler = status_mcp_oauth_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/disconnect")
async def disconnect_mcp_oauth(request: FastAPIRequest):
    handler = disconnect_mcp_oauth_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
