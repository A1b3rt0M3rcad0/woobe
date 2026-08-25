from __future__ import annotations

from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.composition.composers.rerun_agent_run_composer import (
    rerun_agent_run_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/runtime/runs", tags=["runtime", "agent-runs"])


@router.post("/{run_id}/rerun", status_code=201)
async def rerun_agent_run(request: FastAPIRequest):
    response = await request_adapter(request, rerun_agent_run_composer())
    return response_adapter(response)
