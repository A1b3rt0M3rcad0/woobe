from uuid import UUID

from fastapi import APIRouter, Request as FastAPIRequest

from modules.chat_surface.composition.composers.session_read_composers import (
    get_chat_surface_activity_composer,
    list_chat_surface_sessions_composer,
)
from modules.chat_surface.composition.composers.surface_mutation_composers import (
    archive_chat_surface_composer,
    disable_chat_surface_composer,
    update_chat_surface_composer,
)
from modules.chat_surface.composition.composers.surface_read_composers import (
    get_chat_surface_composer,
    list_chat_surfaces_composer,
)
from modules.chat_surface.presentation.http import legacy_routes as _legacy
from modules.chat_surface.presentation.schemas import UpdateChatSurfaceRequest
from shared.presentation.http.adapter import request_adapter, response_adapter


_EXTERNAL_RUNTIME_PATHS = {
    "/v1/chat/sessions/{session_id}/surface",
    "/v1/chat/sessions/{session_id}/messages",
    "/v1/chat/sessions/{session_id}/messages:stream",
}
_MIGRATED_CONTROL_PLANE_ROUTES = {
    ("GET", "/chat-surfaces/projects/{project_id}"),
    ("GET", "/chat-surfaces/{surface_id}"),
    ("PATCH", "/chat-surfaces/{surface_id}"),
    ("POST", "/chat-surfaces/{surface_id}/disable"),
    ("POST", "/chat-surfaces/{surface_id}/archive"),
    ("GET", "/chat-surfaces/{surface_id}/sessions"),
    ("GET", "/chat-surfaces/{surface_id}/activity"),
}


def _legacy_route_is_excluded(route) -> bool:
    path = getattr(route, "path", None)
    if path in _EXTERNAL_RUNTIME_PATHS:
        return True
    methods = getattr(route, "methods", None) or set()
    return any((str(method), path) in _MIGRATED_CONTROL_PLANE_ROUTES for method in methods)


router = APIRouter(tags=["chat-surfaces"])
for route in _legacy.router.routes:
    if not _legacy_route_is_excluded(route):
        router.routes.append(route)


@router.get("/chat-surfaces/projects/{project_id}")
async def list_surfaces(project_id: UUID, request: FastAPIRequest):
    del project_id
    response = await request_adapter(request, list_chat_surfaces_composer())
    return response_adapter(response)


@router.get("/chat-surfaces/{surface_id}")
async def get_surface(surface_id: UUID, request: FastAPIRequest):
    del surface_id
    response = await request_adapter(request, get_chat_surface_composer())
    return response_adapter(response)


@router.patch("/chat-surfaces/{surface_id}")
async def update_surface(
    surface_id: UUID,
    payload: UpdateChatSurfaceRequest,
    request: FastAPIRequest,
):
    del surface_id, payload
    response = await request_adapter(request, update_chat_surface_composer())
    return response_adapter(response)


@router.post("/chat-surfaces/{surface_id}/disable")
async def disable_surface(surface_id: UUID, request: FastAPIRequest):
    del surface_id
    response = await request_adapter(request, disable_chat_surface_composer())
    return response_adapter(response)


@router.post("/chat-surfaces/{surface_id}/archive")
async def archive_surface(surface_id: UUID, request: FastAPIRequest):
    del surface_id
    response = await request_adapter(request, archive_chat_surface_composer())
    return response_adapter(response)


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
