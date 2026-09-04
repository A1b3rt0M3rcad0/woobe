from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from modules.network.entrypoint import NetworkBoundaryService, build_network_service
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import ValidationError
from shared.runtime import (
    RunReference,
    RuntimeFrame,
    RuntimeObserver,
    RuntimeStreamGapError,
)
router = APIRouter(prefix="/network", tags=["network", "runtime"])
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _service(request: Request) -> NetworkBoundaryService:
    del request
    return build_network_service()


async def _load_execution(request: Request, execution_id: UUID):
    return await _service(request).authorized_execution(
        execution_id=execution_id,
        principal=getattr(request.state, "principal", None),
    )


async def cancel_network_run(execution_id: UUID, request: Request):
    """Cancel a Network Run after applying the same target-aware attach authorization."""
    execution = await _load_execution(request, execution_id)
    if str(execution.status) in _TERMINAL_STATUSES:
        return {
            "success": True,
            "data": {
                "run_id": str(execution.id),
                "execution_id": str(execution.id),
                "status": str(execution.status),
            },
        }
    await _service(request).request_cancellation(execution.id, execution.project_id)
    return {
        "success": True,
        "data": {
            "run_id": str(execution.id),
            "execution_id": str(execution.id),
            "status": "cancel_requested",
        },
    }


def _durable_state(execution) -> dict:
    return {
        "status": str(execution.status),
        "output": execution.output_message or "",
        "result": (
            {
                "answer": execution.output_message,
                "parsed_output": execution.parsed_output,
                "output_parse_error": execution.output_parse_error,
                "partial": str(execution.status) == "cancelled" and bool(execution.output_message),
                "cancelled": str(execution.status) == "cancelled",
            }
            if execution.output_message is not None
            or execution.parsed_output is not None
            or execution.output_parse_error is not None
            else None
        ),
        "parsed_output": execution.parsed_output,
        "output_parse_error": execution.output_parse_error,
        "trace_id": str(execution.root_trace_id) if execution.root_trace_id else None,
        "project_id": str(execution.project_id),
        "network_id": str(execution.network_id),
        "network_session_id": str(execution.network_session_id),
        "input_message": execution.input_message,
        "failure_code": execution.failure_code,
        "failure_detail": execution.failure_detail,
        "updated_at": (
            execution.completed_at.isoformat()
            if execution.completed_at is not None
            else execution.updated_at.isoformat()
        ),
    }


def network_runtime_sse(frame: RuntimeFrame, execution_id: UUID) -> str:
    payload = dict(frame.data)
    if frame.event_type == "run.state":
        envelope = {
            "protocol_version": 1,
            "sequence": frame.sequence,
            "execution_id": str(execution_id),
            "data": payload,
            "created_at": payload.get("updated_at"),
        }
    else:
        occurred_at = payload.pop("occurred_at", None)
        payload.pop("run_id", None)
        payload.pop("sequence", None)
        envelope = {
            "protocol_version": 1,
            "sequence": frame.sequence,
            "execution_id": str(execution_id),
            "invocation_id": payload.pop("invocation_id", None),
            "parent_invocation_id": payload.pop("parent_invocation_id", None),
            "node_id": payload.pop("node_id", None),
            "agent_id": payload.pop("agent_id", None),
            "depth": payload.pop("depth", None),
            "data": payload,
            "created_at": occurred_at,
        }
    prefix = f"id: {frame.sequence}\n" if frame.sequence is not None else ""
    return (
        f"{prefix}event: {frame.event_type}\n"
        f"data: {json.dumps(envelope, ensure_ascii=False, default=str)}\n\n"
    )


@router.get("/executions/active")
async def active_network_execution(
    request: Request,
    network_session_id: UUID | None = None,
    network_id: UUID | None = None,
    environment: str | None = None,
):
    if network_session_id is None and network_id is None:
        raise ValidationError("network_session_id or network_id is required")
    if environment is not None and environment not in {"draft", "staging", "production"}:
        raise ValidationError("environment must be draft, staging or production")

    execution = await _service(request).active_execution(
        principal=getattr(request.state, "principal", None),
        network_session_id=network_session_id,
        network_id=network_id,
        environment=environment,
    )
    if execution is None:
        return {"success": True, "data": None}
    return {
        "success": True,
        "data": {
            "run_id": str(execution.id),
            "execution_id": str(execution.id),
            "status": str(execution.status),
            "network_session_id": str(execution.network_session_id),
            "network_id": str(execution.network_id),
            "input_message": execution.input_message,
            "created_at": execution.created_at,
        },
    }


@router.get("/executions/{execution_id}/stream")
async def reattach_network_execution(
    execution_id: UUID,
    request: Request,
) -> StreamingResponse:
    await _load_execution(request, execution_id)
    observer = RuntimeObserver(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        latest = await _load_execution(request, execution_id)
        return _durable_state(latest)

    async def generate():
        try:
            async for frame in observer.observe(
                RunReference.network(execution_id),
                durable_fallback=durable_fallback,
                disconnect_check=request.is_disconnected,
            ):
                yield network_runtime_sse(frame, execution_id)
        except RuntimeStreamGapError:
            latest = await _load_execution(request, execution_id)
            state = _durable_state(latest)
            state.update(
                {
                    "run_id": str(execution_id),
                    "kind": "NETWORK",
                    "sequence": None,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield network_runtime_sse(
                RuntimeFrame("run.state", state, sequence=None),
                execution_id,
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Network-Execution-ID": str(execution_id),
        },
    )
