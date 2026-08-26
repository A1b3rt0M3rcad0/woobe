from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Request
from sqlalchemy import delete, func, select

from modules.network.application.service import NetworkApplicationService
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkSessionModel,
)
from modules.network.infra.database.repositories import NetworkRuntimeRepository
from modules.network.presentation.reattach_routes import (
    _durable_state as _network_durable_state,
    network_runtime_sse,
    reattach_network_execution,
)
from modules.network.presentation.schemas import (
    CreateNetworkSessionRequest,
    EnsureNetworkRequest,
    PromotionRequest,
    RollbackNetworkRequest,
    RunNetworkRequest,
    SaveNetworkDraftRequest,
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


def _network_payload(network) -> dict:
    return {
        "id": str(network.id),
        "project_id": str(network.project_id),
        "name": network.name,
        "description": network.description,
        "draft_definition": network.draft_definition,
        "draft_revision": network.draft_revision,
        "staging_version_id": str(network.staging_version_id)
        if network.staging_version_id
        else None,
        "production_version_id": str(network.production_version_id)
        if network.production_version_id
        else None,
        "created_at": network.created_at,
        "updated_at": network.updated_at,
    }


@router.put("/projects/{project_id}")
async def ensure_network(
    project_id: UUID, payload: EnsureNetworkRequest, request: Request
):
    _authorize_project(request, project_id)
    network = await _service(request).ensure_network(project_id, payload.name)
    return {"success": True, "data": _network_payload(network)}


@router.get("/projects/{project_id}")
async def get_network(project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    network = await _service(request).get_network(project_id)
    return {"success": True, "data": _network_payload(network)}


@router.patch("/{network_id}/draft")
async def save_network_draft(
    network_id: UUID,
    payload: SaveNetworkDraftRequest,
    request: Request,
):
    _authorize_project(request, payload.project_id)
    network = await _service(request).save_draft(
        network_id=network_id,
        project_id=payload.project_id,
        expected_revision=payload.expected_revision,
        name=payload.name,
        description=payload.description,
        definition=payload.definition,
    )
    return {
        "success": True,
        "data": _network_payload(network),
        "revision": network.draft_revision,
    }


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


@router.post("/{network_id}/sessions", status_code=201)
async def create_network_session(
    network_id: UUID,
    payload: CreateNetworkSessionRequest,
    request: Request,
):
    user_id = _authorize_project(request, payload.project_id)
    principal = request.state.principal
    tenant_id = (
        str(principal.project_id)
        if isinstance(principal, ProjectApiPrincipal)
        else None
    )
    session = await _service(request).create_session(
        network_id=network_id,
        project_id=payload.project_id,
        environment=payload.environment,
        title=payload.title,
        tenant_id=tenant_id,
        user_id=str(user_id) if user_id else None,
        external_session_id=payload.external_session_id,
    )
    return {
        "success": True,
        "data": {
            "id": str(session.id),
            "network_id": str(session.network_id),
            "network_version_id": str(session.network_version_id)
            if session.network_version_id
            else None,
            "environment": session.environment,
            "title": session.title,
            "status": session.status,
            "last_message_at": session.last_message_at,
            "message_count": 0,
            "trace_count": 0,
            "created_at": session.created_at,
        },
    }


@router.get("/{network_id}/sessions")
async def list_network_sessions(network_id: UUID, project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        message_count = (
            select(func.count(NetworkMessageModel.id))
            .where(
                NetworkMessageModel.network_session_id == NetworkSessionModel.id
            )
            .correlate(NetworkSessionModel)
            .scalar_subquery()
        )
        execution_count = (
            select(func.count(NetworkExecutionModel.id))
            .where(
                NetworkExecutionModel.network_session_id == NetworkSessionModel.id
            )
            .correlate(NetworkSessionModel)
            .scalar_subquery()
        )
        result = await session.execute(
            select(
                NetworkSessionModel,
                message_count.label("message_count"),
                execution_count.label("trace_count"),
            )
            .where(
                NetworkSessionModel.network_id == network_id,
                NetworkSessionModel.project_id == project_id,
            )
            .order_by(NetworkSessionModel.created_at.desc())
            .limit(100)
        )
        items = list(result.all())
    return {
        "success": True,
        "data": [
            {
                "id": str(item.id),
                "network_version_id": str(item.network_version_id)
                if item.network_version_id
                else None,
                "environment": item.environment,
                "title": item.title,
                "status": item.status,
                "last_message_at": item.last_message_at,
                "created_at": item.created_at,
                "message_count": int(message_count_value or 0),
                "trace_count": int(trace_count_value or 0),
            }
            for item, message_count_value, trace_count_value in items
        ],
    }


@router.get("/{network_id}/sessions/{network_session_id}/messages")
async def list_network_session_messages(
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
    request: Request,
    offset: int = 0,
    limit: int = 200,
):
    _authorize_project(request, project_id)
    safe_offset = max(0, offset)
    safe_limit = min(500, max(1, limit))
    async with request.app.state.session_factory() as session:
        network_session = await session.get(NetworkSessionModel, network_session_id)
        if (
            network_session is None
            or network_session.network_id != network_id
            or network_session.project_id != project_id
        ):
            raise NotFoundError("Network Session not found")
        result = await session.execute(
            select(NetworkMessageModel, NetworkExecutionModel)
            .outerjoin(
                NetworkExecutionModel,
                NetworkExecutionModel.id == NetworkMessageModel.network_execution_id,
            )
            .where(
                NetworkMessageModel.network_session_id == network_session_id,
                NetworkMessageModel.project_id == project_id,
            )
            .order_by(NetworkMessageModel.created_at.asc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        rows = list(result.all())
        execution_ids = {
            execution.id for _, execution in rows if execution is not None
        }
        events_by_execution: dict[UUID, list[dict]] = defaultdict(list)
        if execution_ids:
            event_result = await session.execute(
                select(NetworkExecutionEventModel)
                .where(
                    NetworkExecutionEventModel.network_execution_id.in_(execution_ids)
                )
                .order_by(
                    NetworkExecutionEventModel.network_execution_id,
                    NetworkExecutionEventModel.sequence,
                )
            )
            for event in event_result.scalars():
                events_by_execution[event.network_execution_id].append(
                    {
                        "id": str(event.id),
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "invocation_id": str(event.invocation_id)
                        if event.invocation_id
                        else None,
                        "parent_invocation_id": str(event.parent_invocation_id)
                        if event.parent_invocation_id
                        else None,
                        "node_id": str(event.node_id) if event.node_id else None,
                        "agent_id": str(event.agent_id) if event.agent_id else None,
                        "depth": event.depth,
                        "data": event.payload,
                        "created_at": event.created_at,
                    }
                )
    return {
        "success": True,
        "data": [
            {
                "id": str(message.id),
                "network_execution_id": str(message.network_execution_id)
                if message.network_execution_id
                else None,
                "role": message.role,
                "content": message.content,
                "data": message.data,
                "created_at": message.created_at,
                "execution": (
                    {
                        "id": str(execution.id),
                        "status": execution.status,
                        "draft_revision": execution.draft_revision,
                        "network_version_id": str(execution.network_version_id)
                        if execution.network_version_id
                        else None,
                        "root_trace_id": str(execution.root_trace_id)
                        if execution.root_trace_id
                        else None,
                        "failure_code": execution.failure_code,
                        "failure": next(
                            (
                                event["data"]
                                for event in reversed(events_by_execution[execution.id])
                                if event["event_type"] == "execution_failed"
                            ),
                            None,
                        ),
                        "started_at": execution.started_at,
                        "completed_at": execution.completed_at,
                        "events": events_by_execution[execution.id],
                    }
                    if execution is not None
                    else None
                ),
            }
            for message, execution in rows
        ],
    }


@router.post("/{network_id}/sessions/{network_session_id}/reset-context")
async def reset_network_session_context(
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session, session.begin():
        network_session = await session.get(
            NetworkSessionModel,
            network_session_id,
            with_for_update=True,
        )
        if (
            network_session is None
            or network_session.network_id != network_id
            or network_session.project_id != project_id
        ):
            raise NotFoundError("Network Session not found")
        active = await session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.status.in_(
                    {"queued", "running", "cancel_requested"}
                ),
            )
        )
        if active is not None:
            from shared.infra.errors import ConflictError

            raise ConflictError("Wait for the active execution before resetting context")
        await session.execute(
            delete(NetworkAgentContextModel).where(
                NetworkAgentContextModel.network_session_id == network_session_id
            )
        )
    return {"success": True, "data": {"network_session_id": str(network_session_id)}}


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


@router.get("/executions/{execution_id}/events")
async def list_execution_events(
    execution_id: UUID,
    project_id: UUID,
    request: Request,
    after_sequence: int = 0,
):
    _authorize_project(request, project_id)
    async with request.app.state.session_factory() as session:
        execution = await session.get(NetworkExecutionModel, execution_id)
        if execution is None or execution.project_id != project_id:
            raise NotFoundError("Network execution not found")
        events = await NetworkRuntimeRepository(session).list_events_after(
            execution_id,
            after_sequence,
        )
    return {
        "success": True,
        "data": [
            {
                "id": str(event.id),
                "sequence": event.sequence,
                "event_type": event.event_type,
                "invocation_id": str(event.invocation_id)
                if event.invocation_id
                else None,
                "parent_invocation_id": str(event.parent_invocation_id)
                if event.parent_invocation_id
                else None,
                "node_id": str(event.node_id) if event.node_id else None,
                "agent_id": str(event.agent_id) if event.agent_id else None,
                "depth": event.depth,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@router.post("/executions/{execution_id}/cancel", status_code=202)
async def cancel_execution(execution_id: UUID, project_id: UUID, request: Request):
    _authorize_project(request, project_id)
    await _service(request).request_cancellation(execution_id, project_id)
    return {"success": True, "data": {"execution_id": str(execution_id)}}
