from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Request

from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.presentation.reattach_routes import (
    _durable_state as _network_durable_state,
    network_runtime_sse,
    reattach_network_execution,
)
from modules.network.presentation.schemas import (
    PromotionRequest,
    RollbackNetworkRequest,
    RunNetworkRequest,
)
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.runtime_reattach import RuntimeStreamFrame, RuntimeStreamGapError, RuntimeStreamReader
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/network", tags=["network"])
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _service(request: Request) -> NetworkApplicationService:
    settings = request.app.state.settings
    return NetworkApplicationService(
        request.app.state.session_factory,
        hard_max_depth=settings.network_max_depth_hard,
        hard_max_invocations=settings.network_max_invocations_hard,
        hard_timeout_seconds=settings.network_timeout_hard_seconds,
    )


def _authorize_project(request: Request, project_id: UUID) -> UUID | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return None
    if isinstance(principal, AuthenticatedPrincipal):
        return principal.user_id
    raise AuthorizationError("Authentication required")


@router.post("/{network_id}/promotions/preview")
async def preview_promotion(
    network_id: UUID,
    payload: PromotionRequest,
    request: Request,
):
    _authorize_project(request, payload.project_id)
    result = await _service(request).preview_promotion(
        network_id=network_id,
        project_id=payload.project_id,
        environment=payload.environment,
    )
    return {"success": True, "data": result}


@router.post("/{network_id}/promotions", status_code=201)
async def promote_network(
    network_id: UUID,
    payload: PromotionRequest,
    request: Request,
):
    user_id = _authorize_project(request, payload.project_id)
    version = await _service(request).promote(
        network_id=network_id,
        project_id=payload.project_id,
        environment=payload.environment,
        created_by=user_id,
        expected_revision=payload.expected_revision,
        expected_network_version_id=payload.expected_network_version_id,
        approved_action_ids=payload.approved_action_ids,
    )
    return {
        "success": True,
        "data": {
            "id": str(version.id),
            "kind": version.kind,
            "version": version.version,
            "composition_hash": version.composition_hash,
            "definition": version.definition,
            "resolved_bindings": version.resolved_bindings,
        },
    }


@router.get("/{network_id}/versions")
async def list_network_versions(network_id: UUID, project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    versions = await _service(request).list_versions(network_id, project_id)
    return {
        "success": True,
        "data": [
            {
                "id": str(item.id),
                "kind": item.kind,
                "version": item.version,
                "composition_hash": item.composition_hash,
                "definition": item.definition,
                "resolved_bindings": item.resolved_bindings,
                "created_at": item.created_at,
            }
            for item in versions
        ],
    }


@router.post("/{network_id}/rollback", status_code=201)
async def rollback_network_production(
    network_id: UUID,
    payload: RollbackNetworkRequest,
    request: Request,
):
    user_id = _authorize_project(request, payload.project_id)
    version = await _service(request).rollback_production(
        network_id=network_id,
        project_id=payload.project_id,
        target_version_id=payload.target_version_id,
        created_by=user_id,
    )
    return {
        "success": True,
        "data": {
            "id": str(version.id),
            "kind": version.kind,
            "version": version.version,
            "composition_hash": version.composition_hash,
            "definition": version.definition,
            "resolved_bindings": version.resolved_bindings,
            "created_at": version.created_at,
        },
    }


async def _execution_stream(
    request: Request,
    execution_id: UUID,
    project_id: UUID,
    start_sequence: int,
) -> AsyncIterator[str]:
    # This compatibility helper is still used by ChatSurface, but realtime events
    # now live in the canonical Redis Run stream. PostgreSQL is terminal history.
    del start_sequence
    async with request.app.state.session_factory() as session:
        initial = await session.get(NetworkExecutionModel, execution_id)
    if initial is None or initial.project_id != project_id:
        raise NotFoundError("Network execution not found")

    reader = RuntimeStreamReader(
        EXECUTION_STATE_STORE,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        async with request.app.state.session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None or execution.project_id != project_id:
            raise NotFoundError("Network execution not found")
        return _network_durable_state(execution)

    hot = await EXECUTION_STATE_STORE.get(execution_id)
    if hot is None and str(initial.status) not in TERMINAL_STATUSES:
        queued = _network_durable_state(initial)
        queued.update(
            {
                "run_id": str(execution_id),
                "kind": "NETWORK",
                "sequence": 0,
                "realtime_available": False,
            }
        )
        yield network_runtime_sse(
            RuntimeStreamFrame("run.state", queued, sequence=0),
            execution_id,
        )
        while hot is None:
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.25)
            async with request.app.state.session_factory() as session:
                latest = await session.get(NetworkExecutionModel, execution_id)
            if latest is None or latest.project_id != project_id:
                raise NotFoundError("Network execution not found")
            if str(latest.status) in TERMINAL_STATUSES:
                terminal = _network_durable_state(latest)
                terminal.update(
                    {
                        "run_id": str(execution_id),
                        "kind": "NETWORK",
                        "sequence": 0,
                        "realtime_available": False,
                    }
                )
                yield network_runtime_sse(
                    RuntimeStreamFrame("run.state", terminal, sequence=0),
                    execution_id,
                )
                return
            hot = await EXECUTION_STATE_STORE.get(execution_id)

    try:
        async for frame in reader.stream(
            execution_id,
            "network",
            durable_fallback=durable_fallback,
        ):
            if await request.is_disconnected():
                return
            yield network_runtime_sse(frame, execution_id)
    except RuntimeStreamGapError:
        durable = await durable_fallback()
        if durable is None:
            raise
        degraded = {
            **durable,
            "run_id": str(execution_id),
            "kind": "NETWORK",
            "sequence": 0,
            "realtime_available": False,
            "degraded_reason": "runtime_event_gap",
        }
        yield network_runtime_sse(
            RuntimeStreamFrame("run.state", degraded, sequence=0),
            execution_id,
        )


@router.post("/{network_id}/executions/stream")
async def run_network_stream(
    network_id: UUID,
    payload: RunNetworkRequest,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    _authorize_project(request, payload.project_id)
    execution = await _service(request).submit_execution(
        network_id=network_id,
        project_id=payload.project_id,
        network_session_id=payload.network_session_id,
        message=payload.message,
        idempotency_key=payload.idempotency_key,
        expected_draft_revision=payload.expected_draft_revision,
    )
    # The POST is only create+observe convenience. From Acceptance onward the
    # canonical Redis-backed Run stream owns realtime delivery; Last-Event-ID is
    # replaced by current-state reconciliation plus a live tail.
    del last_event_id
    return await reattach_network_execution(execution.id, request)


@router.post("/executions/{execution_id}/cancel", status_code=202)
async def cancel_execution(execution_id: UUID, project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    await _service(request).request_cancellation(execution_id, project_id)
    return {"success": True, "data": {"execution_id": str(execution_id)}}
