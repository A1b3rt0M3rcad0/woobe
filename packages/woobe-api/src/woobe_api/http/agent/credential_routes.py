from modules.agent.entrypoint import (RotateProviderCredentialInput)
from woobe_api.http.shared.openapi_contracts import request_body_contract
from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import (
    rotate_provider_credential_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter


router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.post("/credentials/{credential_id}/rotate", openapi_extra=request_body_contract(RotateProviderCredentialInput, '/ai/credentials/{credential_id}/rotate', 'post', required=True))
async def rotate_provider_credential(request: FastAPIRequest):
    handler = rotate_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)

