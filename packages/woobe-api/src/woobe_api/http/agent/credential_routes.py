from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import (
    rotate_provider_credential_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.post("/credentials/{credential_id}/rotate")
async def rotate_provider_credential(request: FastAPIRequest):
    handler = rotate_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)

