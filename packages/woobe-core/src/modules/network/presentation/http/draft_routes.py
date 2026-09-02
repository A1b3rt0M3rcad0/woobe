from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.network.composition.composers.draft_composers import (
    save_network_draft_composer,
)
from modules.network.presentation.schemas import SaveNetworkDraftRequest
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


@router.patch("/{network_id}/draft")
async def save_network_draft(
    network_id: UUID,
    payload: SaveNetworkDraftRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    response = await request_adapter(request, save_network_draft_composer())
    return response_adapter(response)
