from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.composition.composers.agent_run_context_composer import (
    agent_run_context_by_trace_composer,
    agent_run_context_composer,
    agent_run_detail_by_trace_composer,
    agent_run_detail_composer,
)
from modules.agent.composition.composers.agent_run_reattach_composer import (
    active_agent_run_composer,
    attach_agent_run_composer,
    cancel_agent_run_composer,
)
from modules.agent.composition.composers.rerun_agent_run_composer import (
    rerun_agent_run_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/runtime/runs", tags=["runtime", "agent-runs"])


@router.get("/active")
async def active_agent_run(
    request: FastAPIRequest,
    session_id: UUID,
):
    handler = active_agent_run_composer()
    return await handler(request, session_id)


@router.get("/by-trace/{trace_id}/model-invocations")
async def list_agent_run_model_invocations_by_trace(
    trace_id: UUID,
    request: FastAPIRequest,
):
    del trace_id
    response = await request_adapter(request, agent_run_context_by_trace_composer())
    return response_adapter(response)


@router.get("/by-trace/{trace_id}")
async def get_agent_run_by_trace(
    trace_id: UUID,
    request: FastAPIRequest,
):
    del trace_id
    response = await request_adapter(request, agent_run_detail_by_trace_composer())
    return response_adapter(response)


@router.get("/{run_id}/model-invocations")
async def list_agent_run_model_invocations(
    run_id: UUID,
    request: FastAPIRequest,
):
    del run_id
    response = await request_adapter(request, agent_run_context_composer())
    return response_adapter(response)


@router.get("/{run_id}")
async def get_agent_run(
    run_id: UUID,
    request: FastAPIRequest,
):
    del run_id
    response = await request_adapter(request, agent_run_detail_composer())
    return response_adapter(response)


@router.get("/{run_id}/stream")
async def attach_agent_run(
    run_id: UUID,
    request: FastAPIRequest,
) -> StreamingResponse:
    handler = attach_agent_run_composer()
    return await handler(run_id, request)


@router.post("/{run_id}/cancel", status_code=202)
async def cancel_agent_run(run_id: UUID, request: FastAPIRequest):
    handler = cancel_agent_run_composer()
    return await handler(run_id, request)


@router.post("/{run_id}/rerun", status_code=201)
async def rerun_agent_run(request: FastAPIRequest):
    response = await request_adapter(request, rerun_agent_run_composer())
    return response_adapter(response)
