from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.composition.composers.tools_composers import (
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
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/mcp/discover")
async def discover_mcp_tools(request: FastAPIRequest):
    handler = discover_mcp_tools_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/refresh")
async def refresh_mcp_tools(request: FastAPIRequest):
    handler = refresh_mcp_tools_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/mcp/permissions")
async def update_mcp_permissions(request: FastAPIRequest):
    handler = update_mcp_tool_permissions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/permissions/bulk")
async def bulk_update_mcp_permissions(request: FastAPIRequest):
    handler = bulk_update_mcp_tool_permissions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/start")
async def start_mcp_oauth(request: FastAPIRequest):
    handler = start_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/complete")
async def complete_mcp_oauth(request: FastAPIRequest):
    handler = complete_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/start")
async def start_mcp_oauth_device(request: FastAPIRequest):
    handler = start_mcp_oauth_device_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/device/poll")
async def poll_mcp_oauth_device(request: FastAPIRequest):
    handler = poll_mcp_oauth_device_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/status")
async def status_mcp_oauth(request: FastAPIRequest):
    handler = status_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/mcp/oauth/disconnect")
async def disconnect_mcp_oauth(request: FastAPIRequest):
    handler = disconnect_mcp_oauth_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
