from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.application.composers.tools_composers import discover_mcp_tools_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/mcp/discover")
async def discover_mcp_tools(request: FastAPIRequest):
    handler = discover_mcp_tools_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
