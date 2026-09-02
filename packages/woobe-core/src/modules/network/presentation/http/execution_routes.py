from uuid import UUID

from fastapi import APIRouter, Header, Request as FastAPIRequest

from modules.network.composition.composers.execution_composers import (
    accept_network_execution_composer,
)
from modules.network.composition.composers.execution_control_composers import (
    cancel_network_execution_composer,
)
from modules.network.presentation.reattach_routes import reattach_network_execution
from modules.network.presentation.schemas import RunNetworkRequest
from shared.presentation.http.adapter import request_adapter


router = APIRouter(prefix="/network", tags=["network", "runtime"])


@router.post("/{network_id}/executions/stream")
async def run_network_stream(
    network_id: UUID,
    payload: RunNetworkRequest,
    request: FastAPIRequest,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    del network_id, payload, last_event_id
    accepted = await request_adapter(request, accept_network_execution_composer())
    execution_id = UUID(str(accepted.body["data"]["execution_id"]))
    return await reattach_network_execution(execution_id, request)


@router.post("/executions/{execution_id}/cancel", status_code=202)
async def cancel_network_execution(
    execution_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del execution_id, project_id
    return await request_adapter(request, cancel_network_execution_composer())
