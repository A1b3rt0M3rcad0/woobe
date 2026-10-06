from modules.agent.entrypoint import McpOAuthStartInput, McpOAuthCompleteInput, McpOAuthDeviceStartInput, McpOAuthDevicePollInput, McpOAuthStatusInput, McpOAuthDisconnectInput
from modules.agent.entrypoint import (UpdateMcpToolPermissionsInput, BulkUpdateMcpToolPermissionsInput)
from modules.agent.entrypoint import (McpDiscoverInput, RefreshMcpProviderToolsInput)
from woobe_api.http.shared.openapi_contracts import request_body_contract
from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import (
    bulk_update_mcp_tool_permissions_composer,
    complete_mcp_oauth_composer,
    disconnect_mcp_oauth_composer,
    discover_mcp_tools_composer,
    poll_mcp_oauth_device_composer,
    refresh_mcp_tools_composer,
    start_mcp_oauth_composer,
    start_mcp_oauth_device_composer,
    status_mcp_oauth_composer,
    update_mcp_tool_permissions_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/mcp/discover", openapi_extra=request_body_contract(McpDiscoverInput, '/tools/mcp/discover', 'post', required=True))
async def discover_mcp_tools(request: FastAPIRequest):
    handler = discover_mcp_tools_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/refresh", openapi_extra=request_body_contract(RefreshMcpProviderToolsInput, '/tools/mcp/refresh', 'post', required=True))
async def refresh_mcp_tools(request: FastAPIRequest):
    handler = refresh_mcp_tools_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/mcp/permissions", openapi_extra=request_body_contract(UpdateMcpToolPermissionsInput, '/tools/mcp/permissions', 'patch', required=False))
async def update_mcp_permissions(request: FastAPIRequest):
    handler = update_mcp_tool_permissions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/permissions/bulk", openapi_extra=request_body_contract(BulkUpdateMcpToolPermissionsInput, '/tools/mcp/permissions/bulk', 'post', required=True))
async def bulk_update_mcp_permissions(request: FastAPIRequest):
    handler = bulk_update_mcp_tool_permissions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/start", openapi_extra=request_body_contract(McpOAuthStartInput, "/tools/mcp/oauth/start", "post"))
async def start_mcp_oauth(request: FastAPIRequest):
    handler = start_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/complete", openapi_extra=request_body_contract(McpOAuthCompleteInput, "/tools/mcp/oauth/complete", "post"))
async def complete_mcp_oauth(request: FastAPIRequest):
    handler = complete_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/start", openapi_extra=request_body_contract(McpOAuthDeviceStartInput, "/tools/mcp/oauth/device/start", "post"))
async def start_mcp_oauth_device(request: FastAPIRequest):
    handler = start_mcp_oauth_device_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/poll", openapi_extra=request_body_contract(McpOAuthDevicePollInput, "/tools/mcp/oauth/device/poll", "post"))
async def poll_mcp_oauth_device(request: FastAPIRequest):
    handler = poll_mcp_oauth_device_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/status", openapi_extra=request_body_contract(McpOAuthStatusInput, "/tools/mcp/oauth/status", "post"))
async def status_mcp_oauth(request: FastAPIRequest):
    handler = status_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/disconnect", openapi_extra=request_body_contract(McpOAuthDisconnectInput, "/tools/mcp/oauth/disconnect", "post"))
async def disconnect_mcp_oauth(request: FastAPIRequest):
    handler = disconnect_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)

