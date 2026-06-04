from fastapi import APIRouter, Request as FastAPIRequest

from modules.ai.application.composers.create_provider_credential_composer import create_provider_credential_composer
from modules.ai.application.composers.list_provider_credentials_composer import list_provider_credentials_composer
from modules.ai.application.composers.create_agent_composer import create_agent_composer
from modules.ai.application.composers.list_agents_composer import list_agents_composer
from modules.ai.application.composers.get_agent_composer import get_agent_composer
from modules.ai.application.composers.update_agent_composer import update_agent_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/credentials")
async def create_provider_credential(request: FastAPIRequest):
    handler = create_provider_credential_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/credentials")
async def list_provider_credentials(request: FastAPIRequest):
    handler = list_provider_credentials_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents")
async def create_agent(request: FastAPIRequest):
    handler = create_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents")
async def list_agents(request: FastAPIRequest):
    handler = list_agents_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}")
async def get_agent(request: FastAPIRequest):
    handler = get_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}")
async def update_agent(request: FastAPIRequest):
    handler = update_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
