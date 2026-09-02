from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest, status

from modules.agent.entrypoint import (
    NetworkAgentAvailabilityReader,
    NetworkAgentPromotionGateway,
)
from modules.core.entrypoint import CoreProjectLookup
from modules.network.entrypoint import (
    EnsureNetworkRequest,
    PromotionRequest,
    SaveNetworkDraftRequest,
    build_ensure_project_network_handler,
    build_get_legacy_project_network_handler,
    build_preview_network_promotion_handler,
    build_promote_network_handler,
    build_save_network_draft_handler,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(tags=["network"])


def _agent_promotion_gateway(transaction):
    return NetworkAgentPromotionGateway(transaction)


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.put("/network/projects/{project_id}")
async def ensure_network(
    project_id: UUID,
    payload: EnsureNetworkRequest,
    request: FastAPIRequest,
):
    del project_id, payload
    return await _handle(
        request,
        build_ensure_project_network_handler(CoreProjectLookup()),
    )


@router.get("/network/projects/{project_id}")
async def get_network(project_id: UUID, request: FastAPIRequest):
    del project_id
    return await _handle(request, build_get_legacy_project_network_handler())


@router.patch("/network/{network_id}/draft")
async def save_network_draft(
    network_id: UUID,
    payload: SaveNetworkDraftRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(
        request,
        build_save_network_draft_handler(NetworkAgentAvailabilityReader()),
    )


@router.post("/network/{network_id}/promotions/preview")
async def preview_promotion(
    network_id: UUID,
    payload: PromotionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(
        request,
        build_preview_network_promotion_handler(_agent_promotion_gateway),
    )


@router.post(
    "/network/{network_id}/promotions",
    status_code=status.HTTP_201_CREATED,
)
async def promote_network(
    network_id: UUID,
    payload: PromotionRequest,
    request: FastAPIRequest,
):
    del network_id, payload
    return await _handle(
        request,
        build_promote_network_handler(_agent_promotion_gateway),
    )


__all__ = ["router"]
