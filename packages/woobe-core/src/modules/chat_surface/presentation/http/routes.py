from fastapi import APIRouter

from modules.chat_surface.presentation.http import legacy_routes as _legacy


_EXTERNAL_RUNTIME_PATHS = {
    "/v1/chat/sessions/{session_id}/surface",
    "/v1/chat/sessions/{session_id}/messages",
    "/v1/chat/sessions/{session_id}/messages:stream",
}

router = APIRouter(tags=["chat-surfaces"])
for route in _legacy.router.routes:
    if getattr(route, "path", None) not in _EXTERNAL_RUNTIME_PATHS:
        router.routes.append(route)


def __getattr__(name: str):
    return getattr(_legacy, name)


__all__ = ["router"]
