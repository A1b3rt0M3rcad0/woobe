from uuid import UUID

from modules.chat_surface.application.dtos.surface_read import (
    ChatSurfaceState,
    GetChatSurfaceInput,
    ListChatSurfacesInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from modules.chat_surface.presentation.schemas import normalize_appearance_config
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


def _surface_payload(surface: ChatSurfaceState) -> dict:
    return {
        "id": str(surface.id),
        "public_id": surface.public_id,
        "project_id": str(surface.project_id),
        "name": surface.name,
        "description": surface.description,
        "target_type": surface.target_type,
        "target_id": str(surface.target_id),
        "target_release_id": str(surface.target_release_id),
        "environment": surface.environment,
        "status": surface.status,
        "access_mode": surface.access_mode,
        "allowed_origins": list(surface.allowed_origins),
        "appearance_config": normalize_appearance_config(surface.appearance_config),
        "requests_per_minute": surface.requests_per_minute,
        "max_concurrent_runs": surface.max_concurrent_runs,
        "session_token_ttl_seconds": surface.session_token_ttl_seconds,
        "token_epoch": surface.token_epoch,
        "activated_at": surface.activated_at,
        "archived_at": surface.archived_at,
        "created_at": surface.created_at,
        "updated_at": surface.updated_at,
    }


class ListChatSurfacesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            ListChatSurfacesInput(
                project_id=UUID(str(request.path_params["project_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [_surface_payload(item) for item in result],
            },
        )


class GetChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetChatSurfaceInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": _surface_payload(result)},
        )
