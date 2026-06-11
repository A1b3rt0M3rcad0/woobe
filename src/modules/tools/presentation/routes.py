from fastapi import APIRouter, Request as FastAPIRequest

from modules.tools.application.composers.list_tools_composer import list_tools_composer
from modules.tools.application.composers.create_tool_composer import create_tool_composer
from modules.tools.application.composers.update_tool_composer import update_tool_composer
from modules.tools.application.composers.update_tool_status_composer import update_tool_status_composer
from modules.tools.application.composers.delete_tool_composer import delete_tool_composer
from modules.tools.application.composers.test_tool_composer import test_tool_composer
from modules.tools.application.composers.execute_tool_composer import execute_tool_composer
from modules.tools.application.composers.list_tools_by_agent_composer import list_tools_by_agent_composer
from modules.tools.application.composers.list_secrets_composer import list_secrets_composer
from modules.tools.application.composers.create_secret_composer import create_secret_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/tools")
async def list_tools(request: FastAPIRequest):
    handler = list_tools_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/tools")
async def create_tool(request: FastAPIRequest):
    handler = create_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/tools/{tool_id}")
async def update_tool(request: FastAPIRequest):
    handler = update_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/tools/{tool_id}/status")
async def update_tool_status(request: FastAPIRequest):
    handler = update_tool_status_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/tools/{tool_id}")
async def delete_tool(request: FastAPIRequest):
    handler = delete_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/tools/test")
async def test_tool(request: FastAPIRequest):
    handler = test_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/tools/execute")
async def execute_tool(request: FastAPIRequest):
    handler = execute_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/tools")
async def list_tools_by_agent(request: FastAPIRequest):
    handler = list_tools_by_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/secrets")
async def list_secrets(request: FastAPIRequest):
    handler = list_secrets_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/secrets")
async def create_secret(request: FastAPIRequest):
    handler = create_secret_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
