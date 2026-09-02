from uuid import UUID

from fastapi import APIRouter, Request

from modules.network.composition.composers.run_reattach_composer import (
    active_network_run_composer,
    attach_network_run_composer,
)


router = APIRouter(prefix="/network", tags=["network", "runtime"])


@router.get("/executions/active")
async def active_network_execution(
    request: Request,
    network_session_id: UUID | None = None,
    network_id: UUID | None = None,
    environment: str | None = None,
):
    return await active_network_run_composer()(
        request,
        network_session_id=network_session_id,
        network_id=network_id,
        environment=environment,
    )


@router.get("/executions/{execution_id}/stream")
async def reattach_network_execution(
    execution_id: UUID,
    request: Request,
):
    return await attach_network_run_composer()(execution_id, request)
