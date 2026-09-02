from uuid import UUID

from fastapi import APIRouter, Header, Request as FastAPIRequest

from modules.network.composition.composers.rerun_composer import (
    rerun_network_execution_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network/executions", tags=["network", "runtime"])


@router.post("/{execution_id}/rerun", status_code=201)
async def rerun_network_execution(
    request: FastAPIRequest,
    execution_id: UUID,
    project_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    del execution_id, project_id, idempotency_key
    response = await request_adapter(request, rerun_network_execution_composer())
    return response_adapter(response)
