from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.composition.composers.rotate_provider_credential_composer import (
    rotate_provider_credential_composer,
)
from modules.agent.infra.database.database import AgentDatabase
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.post("/credentials/{credential_id}/rotate")
async def rotate_provider_credential(request: FastAPIRequest):
    database = AgentDatabase(request.app.state.session_factory)
    handler = rotate_provider_credential_composer(
        database,
        request.app.state.settings,
    )
    response = await request_adapter(request, handler)
    return response_adapter(response)
