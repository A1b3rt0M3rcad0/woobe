from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.network.composition.composers.compatibility_composers import (
    ensure_project_network_composer,
    get_legacy_project_network_composer,
)
from modules.network.presentation.schemas import EnsureNetworkRequest
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network/projects", tags=["network"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.put("/{project_id}")
async def ensure_network(
    project_id: UUID,
    payload: EnsureNetworkRequest,
    request: FastAPIRequest,
):
    del project_id, payload
    return await _handle(request, ensure_project_network_composer())


@router.get("/{project_id}")
async def get_network(project_id: UUID, request: FastAPIRequest):
    del project_id
    return await _handle(request, get_legacy_project_network_composer())
