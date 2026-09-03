from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import NetworkExecutionModel, NetworkSessionModel
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, NotFoundError, ValidationError
from shared.runtime import (
    RunReference,
    RuntimeFrame,
    RuntimeObserver,
    RuntimeStreamGapError,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal
from shared.security.tenancy import TenantAuthorizer


router = APIRouter(prefix="/network", tags=["network", "runtime"])
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


def _service(request: Request) -> NetworkApplicationService:
    settings = request.app.state.settings
    return NetworkApplicationService(
        request.app.state.session_factory,
        hard_max_depth=settings.network_max_depth_hard,
        hard_max_invocations=settings.network_max_invocations_hard,
        hard_timeout_seconds=settings.network_timeout_hard_seconds,
    )


def _runtime_target(principal: ProjectApiPrincipal) -> tuple[str | None, UUID | None]:
    target_type = principal.target_type
    target_id = principal.target_id
    if target_type is None and principal.agent_id is not None:
        target_type = "agent"
    if target_id is None and principal.agent_id is not None:
        target_id = principal.agent_id
    return target_type, target_id


async def _authorize_execution(
    request: Request,
    execution: NetworkExecutionModel,
    network_session: NetworkSessionModel | None,
    *,
    database=None,
) -> None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != execution.project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        if principal.kind == "runtime":
            target_type, target_id = _runtime_target(principal)
            if target_type != "network" or target_id != execution.network_id:
                raise NotFoundError("Network execution not found")
            if (
                principal.environment is not None
                and (
                    network_session is None
                    or principal.environment != network_session.environment
                )
            ):
                raise NotFoundError("Network execution not found")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        if database is not None:
            await TenantAuthorizer(database).authorize(
                user_id=principal.user_id,
                path_params={},
                query_params={"project_id": execution.project_id},
                body=None,
            )
            return
        async with request.app.state.session_factory() as session:
            await TenantAuthorizer(session).authorize(
                user_id=principal.user_id,
                path_params={},
                query_params={"project_id": execution.project_id},
                body=None,
            )
        return
    raise AuthorizationError("Authentication required")


async def _load_execution(request: Request, execution_id: UUID) -> NetworkExecutionModel:
    async with request.app.state.session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None:
            raise NotFoundError("Network execution not found")
        network_session = await session.get(NetworkSessionModel, execution.network_session_id)
        await _authorize_execution(
            request,
            execution,
            network_session,
            database=session,
        )
        return execution


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


def _durable_state(execution: NetworkExecutionModel) -> dict:
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

    async with request.app.state.session_factory() as session:
        statement = (
            select(NetworkExecutionModel)
            .join(
                NetworkSessionModel,
                NetworkSessionModel.id == NetworkExecutionModel.network_session_id,
            )
            .where(NetworkExecutionModel.status.in_(_ACTIVE_STATUSES))
        )
        if network_session_id is not None:
            statement = statement.where(
                NetworkExecutionModel.network_session_id == network_session_id
            )
        if network_id is not None:
            statement = statement.where(NetworkExecutionModel.network_id == network_id)
        if environment is not None:
            statement = statement.where(NetworkSessionModel.environment == environment)
        execution = await session.scalar(
            statement
            .order_by(NetworkExecutionModel.created_at.desc(), NetworkExecutionModel.id.desc())
            .limit(1)
        )
        network_session = (
            await session.get(NetworkSessionModel, execution.network_session_id)
            if execution is not None
            else None
        )
        if execution is not None:
            await _authorize_execution(
                request,
                execution,
                network_session,
                database=session,
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
    initial = await _load_execution(request, execution_id)
    observer = RuntimeObserver(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        latest = await _load_execution(request, execution_id)
        return _durable_state(latest)

    async def generate():
        hot = await EXECUTION_STATE_STORE.get(execution_id)
        if hot is None and str(initial.status) not in _TERMINAL_STATUSES:
            queued = _durable_state(initial)
            queued.update(
                {
                    "run_id": str(execution_id),
                    "kind": "NETWORK",
                    "sequence": None,
                    "realtime_available": False,
                }
            )
            yield network_runtime_sse(
                RuntimeFrame("run.state", queued, sequence=None),
                execution_id,
            )

            while hot is None:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.25)
                latest = await _load_execution(request, execution_id)
                if str(latest.status) in _TERMINAL_STATUSES:
                    terminal = _durable_state(latest)
                    terminal.update(
                        {
                            "run_id": str(execution_id),
                            "kind": "NETWORK",
                            "sequence": None,
                            "realtime_available": False,
                        }
                    )
                    yield network_runtime_sse(
                        RuntimeFrame("run.state", terminal, sequence=None),
                        execution_id,
                    )
                    return
                hot = await EXECUTION_STATE_STORE.get(execution_id)

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
