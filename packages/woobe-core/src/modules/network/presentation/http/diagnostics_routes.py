from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.network.composition.composers.diagnostics_composer import (
    get_network_run_diagnostics_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


@router.get("/executions/{execution_id}/diagnostics")
async def get_network_run_diagnostics(
    execution_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del execution_id, project_id
    response = await request_adapter(request, get_network_run_diagnostics_composer())
    return response_adapter(response)
