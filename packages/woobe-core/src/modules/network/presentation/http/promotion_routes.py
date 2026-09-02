from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest, status

from modules.network.composition.composers.promotion_composers import (
    preview_network_promotion_composer,
    promote_network_composer,
)
from modules.network.presentation.schemas import PromotionRequest
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/{network_id}/promotions/preview")
async def preview_promotion(
    network_id: UUID,
    payload: PromotionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(request, preview_network_promotion_composer())


@router.post("/{network_id}/promotions", status_code=status.HTTP_201_CREATED)
async def promote_network(
    network_id: UUID,
    payload: PromotionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(request, promote_network_composer())
