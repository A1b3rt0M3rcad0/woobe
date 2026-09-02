from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest, status

from modules.network.composition.composers.session_composers import (
    create_network_session_composer,
)
from modules.network.presentation.schemas import CreateNetworkSessionRequest
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


@router.post("/{network_id}/sessions", status_code=status.HTTP_201_CREATED)
async def create_network_session(
    network_id: UUID,
    payload: CreateNetworkSessionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    response = await request_adapter(request, create_network_session_composer())
    return response_adapter(response)
