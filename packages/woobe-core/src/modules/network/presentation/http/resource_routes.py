from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest, status

from modules.network.composition.composers.resource_composers import (
    create_project_network_composer,
    get_project_network_composer,
    list_project_networks_composer,
    update_project_network_composer,
)
from modules.network.presentation.schemas import (
    CreateNetworkRequest,
    UpdateNetworkMetadataRequest,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network/projects", tags=["network"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/{project_id}/networks")
async def list_project_networks(project_id: UUID, request: FastAPIRequest):
    del project_id
    return await _handle(request, list_project_networks_composer())


@router.post("/{project_id}/networks", status_code=status.HTTP_201_CREATED)
async def create_project_network(
    project_id: UUID,
    payload: CreateNetworkRequest,
    request: FastAPIRequest,
):
    del project_id, payload
    return await _handle(request, create_project_network_composer())


@router.get("/{project_id}/networks/{network_id}")
async def get_project_network(
    project_id: UUID,
    network_id: UUID,
    request: FastAPIRequest,
):
    del project_id, network_id
    return await _handle(request, get_project_network_composer())


@router.patch("/{project_id}/networks/{network_id}")
async def update_project_network_metadata(
    project_id: UUID,
    network_id: UUID,
    payload: UpdateNetworkMetadataRequest,
    request: FastAPIRequest,
):
    del project_id, network_id, payload
    return await _handle(request, update_project_network_composer())
