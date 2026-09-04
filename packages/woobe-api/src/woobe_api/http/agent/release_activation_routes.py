from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import (
    list_release_activations_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai", "agent", "release-history"])


@router.get("/agents/{agent_id}/release-activations")
async def list_agent_release_activations(request: FastAPIRequest):
    handler = list_release_activations_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)

