from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.application.composers.model_lifecycle_composer import (
    credential_usage_composer,
    provider_model_usage_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai", "provider-lifecycle"])


@router.get("/credentials/{credential_id}/usage")
async def provider_credential_usage(request: FastAPIRequest):
    handler = credential_usage_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models/{provider_model_id}/usage")
async def provider_model_usage(request: FastAPIRequest):
    handler = provider_model_usage_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
