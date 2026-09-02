from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest, status

from modules.network.composition.composers.management_composers import (
    activate_network_production_composer,
    get_network_execution_snapshot_composer,
    list_managed_network_versions_composer,
    list_network_activations_composer,
    rollback_network_production_composer,
)
from modules.network.presentation.schemas import (
    ActivateProductionRequest,
    RollbackNetworkRequest,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/{network_id}/management/versions")
async def list_managed_network_versions(
    network_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del network_id, project_id
    return await _handle(request, list_managed_network_versions_composer())


@router.get("/{network_id}/management/activations")
async def list_network_production_activations(
    network_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del network_id, project_id
    return await _handle(request, list_network_activations_composer())


@router.get("/executions/{execution_id}/snapshot")
async def get_network_execution_snapshot(
    execution_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del execution_id, project_id
    return await _handle(request, get_network_execution_snapshot_composer())


@router.post(
    "/{network_id}/production/activations",
    status_code=status.HTTP_201_CREATED,
)
async def activate_network_production(
    network_id: UUID,
    payload: ActivateProductionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(request, activate_network_production_composer())


@router.post("/{network_id}/rollback", status_code=status.HTTP_201_CREATED)
async def rollback_network_production(
    network_id: UUID,
    payload: RollbackNetworkRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(request, rollback_network_production_composer())
