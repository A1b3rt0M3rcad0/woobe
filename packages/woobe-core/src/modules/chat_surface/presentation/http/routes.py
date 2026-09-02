from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.chat_surface.composition.composers.session_read_composers import (
    get_chat_surface_activity_composer,
    list_chat_surface_sessions_composer,
)
from modules.chat_surface.presentation.http import legacy_routes as _legacy
from shared.presentation.http.adapter import request_adapter, response_adapter


_EXTERNAL_RUNTIME_PATHS = {
    "/v1/chat/sessions/{session_id}/surface",
    "/v1/chat/sessions/{session_id}/messages",
    "/v1/chat/sessions/{session_id}/messages:stream",
}
_MIGRATED_CONTROL_PLANE_PATHS = {
    "/chat-surfaces/{surface_id}/sessions",
    "/chat-surfaces/{surface_id}/activity",
}
_EXCLUDED_LEGACY_PATHS = _EXTERNAL_RUNTIME_PATHS | _MIGRATED_CONTROL_PLANE_PATHS

router = APIRouter(tags=["chat-surfaces"])
for route in _legacy.router.routes:
    if getattr(route, "path", None) not in _EXCLUDED_LEGACY_PATHS:
        router.routes.append(route)


@router.get("/chat-surfaces/{surface_id}/sessions")
async def list_surface_sessions(
    surface_id: UUID,
    request: FastAPIRequest,
    limit: int = 50,
):
    del surface_id, limit
    response = await request_adapter(request, list_chat_surface_sessions_composer())
    return response_adapter(response)


@router.get("/chat-surfaces/{surface_id}/activity")
async def get_surface_activity(
    surface_id: UUID,
    request: FastAPIRequest,
):
    del surface_id
    response = await request_adapter(request, get_chat_surface_activity_composer())
    return response_adapter(response)


def __getattr__(name: str):
    return getattr(_legacy, name)


__all__ = ["router"]
