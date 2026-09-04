from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import (
    agent_run_context_by_trace_composer,
    agent_run_context_composer,
    agent_run_detail_by_trace_composer,
    agent_run_detail_composer,
)
from modules.agent.entrypoint import build_agent_run_reattach_operations
from modules.agent.entrypoint import (
    list_agent_runs_composer,
)
from modules.agent.entrypoint import (
    rerun_agent_run_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter
from woobe_api.http.agent.controllers.agent_run_reattach_controller import (
    AgentRunReattachController,
)


router = APIRouter(prefix="/runtime/runs", tags=["runtime", "agent-runs"])


@router.get("")
async def list_agent_runs(
    request: FastAPIRequest,
    project_id: UUID,
    agent_id: UUID,
    session_id: UUID | None = None,
    environment: str | None = None,
    limit: int = 100,
):
    del project_id, agent_id, session_id, environment, limit
    response = await request_adapter(request, list_agent_runs_composer())
    return response_adapter(response)


@router.get("/active")
async def active_agent_run(
    request: FastAPIRequest,
    session_id: UUID,
):
    controller = AgentRunReattachController(build_agent_run_reattach_operations())
    return await controller.active(request, session_id)


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
    controller = AgentRunReattachController(build_agent_run_reattach_operations())
    return await controller.attach(run_id, request)


@router.post("/{run_id}/cancel", status_code=202)
async def cancel_agent_run(run_id: UUID, request: FastAPIRequest):
    controller = AgentRunReattachController(build_agent_run_reattach_operations())
    return await controller.cancel(run_id, request)


@router.post("/{run_id}/rerun", status_code=201)
async def rerun_agent_run(request: FastAPIRequest):
    response = await request_adapter(request, rerun_agent_run_composer())
    return response_adapter(response)
