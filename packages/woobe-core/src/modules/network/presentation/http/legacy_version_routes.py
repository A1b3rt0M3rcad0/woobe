from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.network.composition.composers.legacy_version_composers import (
    list_network_versions_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


@router.get("/{network_id}/versions")
async def list_network_versions(
    network_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del network_id, project_id
    response = await request_adapter(request, list_network_versions_composer())
    return response_adapter(response)
