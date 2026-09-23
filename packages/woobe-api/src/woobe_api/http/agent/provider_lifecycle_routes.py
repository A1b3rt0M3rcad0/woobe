from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.entrypoint import (
    archive_credential_composer,
    archive_provider_model_composer,
    credential_usage_composer,
    provider_model_usage_composer,
    revoke_credential_composer,
    rotate_credential_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai", "provider-lifecycle"])


@router.get("/credentials/{credential_id}/usage")
async def provider_credential_usage(request: FastAPIRequest):
    handler = credential_usage_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/credentials/{credential_id}")
async def archive_provider_credential(request: FastAPIRequest):
    handler = archive_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/credentials/{credential_id}/rotate")
async def rotate_provider_credential(request: FastAPIRequest):
    handler = rotate_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/credentials/{credential_id}/revoke")
async def revoke_provider_credential(request: FastAPIRequest):
    handler = revoke_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/provider-models/{provider_model_id}")
async def archive_provider_model(request: FastAPIRequest):
    handler = archive_provider_model_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models/{provider_model_id}/usage")
async def provider_model_usage(request: FastAPIRequest):
    handler = provider_model_usage_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)

