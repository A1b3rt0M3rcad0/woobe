from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.network.composition.composers.history_composers import (
    list_network_execution_events_composer,
    list_network_session_messages_composer,
    list_network_sessions_composer,
    reset_network_session_context_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


router = APIRouter(prefix="/network", tags=["network"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/{network_id}/sessions")
async def list_network_sessions(
    network_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del network_id, project_id
    return await _handle(request, list_network_sessions_composer())


@router.get("/{network_id}/sessions/{network_session_id}/messages")
async def list_network_session_messages(
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
    offset: int = 0,
    limit: int = 200,
):
    del network_id, network_session_id, project_id, offset, limit
    return await _handle(request, list_network_session_messages_composer())


@router.post("/{network_id}/sessions/{network_session_id}/reset-context")
async def reset_network_session_context(
    network_id: UUID,
    network_session_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
):
    del network_id, network_session_id, project_id
    return await _handle(request, reset_network_session_context_composer())


@router.get("/executions/{execution_id}/events")
async def list_execution_events(
    execution_id: UUID,
    project_id: UUID,
    request: FastAPIRequest,
    after_sequence: int = 0,
):
    del execution_id, project_id, after_sequence
    return await _handle(request, list_network_execution_events_composer())
