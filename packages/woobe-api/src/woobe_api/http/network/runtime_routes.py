from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Request
from modules.network.entrypoint import NetworkBoundaryService, build_network_service
from woobe_api.http.network.reattach_routes import (
    _durable_state as _network_durable_state,
    network_runtime_sse,
    reattach_network_execution,
)
from modules.network.entrypoint import (
    CreateNetworkSessionRequest,
    EnsureNetworkRequest,
    PromotionRequest,
    RollbackNetworkRequest,
    RunNetworkRequest,
    SaveNetworkDraftRequest,
)
from shared.infra.errors import AuthorizationError
from shared.runtime.contracts import runtime_state_frame
from shared.runtime import (
    RunReference,
    RuntimeFrame,
    RuntimeObserver,
    RuntimeStreamGapError,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


router = APIRouter(prefix="/network", tags=["network"])


def _service(request: Request) -> NetworkBoundaryService:
    del request
    return build_network_service()


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
    items = await _service(request).list_sessions(
        network_id=network_id,
        project_id=project_id,
    )
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
                "message_count": message_count_value,
                "trace_count": trace_count_value,
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
    messages = await _service(request).list_session_messages(
        network_id=network_id,
        network_session_id=network_session_id,
        project_id=project_id,
        offset=safe_offset,
        limit=safe_limit,
    )
    return {"success": True, "data": messages}


@router.post("/{network_id}/sessions/{network_session_id}/reset-context")
async def reset_network_session_context(
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
    request: Request,
):
    _authorize_project(request, project_id)
    await _service(request).reset_session_context(
        network_id=network_id,
        network_session_id=network_session_id,
        project_id=project_id,
    )
    return {"success": True, "data": {"network_session_id": str(network_session_id)}}


async def _execution_stream(
    request: Request,
    execution_id: UUID,
    project_id: UUID,
    start_sequence: int,
) -> AsyncIterator[str]:
    del start_sequence
    service = _service(request)
    await service.get_execution(
        execution_id=execution_id,
        project_id=project_id,
    )

    observer = RuntimeObserver(
        request.app.state.execution_state_store,
        heartbeat_seconds=request.app.state.settings.network_stream_heartbeat_seconds,
        block_ms=500,
    )

    async def durable_fallback() -> dict | None:
        execution = await service.get_execution(
            execution_id=execution_id,
            project_id=project_id,
        )
        return _network_durable_state(execution)

    try:
        async for frame in observer.observe(
            RunReference.network(execution_id),
            durable_fallback=durable_fallback,
            disconnect_check=request.is_disconnected,
        ):
            yield network_runtime_sse(frame, execution_id)
    except RuntimeStreamGapError:
        durable = await durable_fallback()
        if durable is None:
            raise
        degraded = {
            **durable,
            "run_id": str(execution_id),
            "kind": "NETWORK",
            "sequence": None,
            "realtime_available": False,
            "degraded_reason": "runtime_event_gap",
        }
        yield network_runtime_sse(
            runtime_state_frame(degraded),
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
        external_context=payload.external_context,
        idempotency_key=payload.idempotency_key,
        expected_draft_revision=payload.expected_draft_revision,
    )
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
    events = await _service(request).list_execution_events(
        execution_id=execution_id,
        project_id=project_id,
        after_sequence=after_sequence,
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
