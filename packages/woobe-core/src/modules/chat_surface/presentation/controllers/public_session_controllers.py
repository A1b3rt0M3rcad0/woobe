from uuid import UUID

from modules.chat_surface.application.dtos.public_session import (
    ArchiveChatSurfaceSessionBindingInput,
    ChatSurfaceSessionBindingState,
    CreateChatSurfaceSessionBindingInput,
    GetChatSurfaceSessionBindingInput,
    GetChatSurfaceSessionByIdempotencyInput,
    IssueChatSurfaceSessionTokenInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


def _binding_payload(binding: ChatSurfaceSessionBindingState) -> dict:
    return {
        "id": str(binding.id),
        "chat_surface_id": str(binding.chat_surface_id),
        "session_id": str(binding.session_id),
        "target_type": binding.target_type,
        "target_id": str(binding.target_id),
        "target_release_id": str(binding.target_release_id),
        "external_reference": binding.external_reference,
        "status": binding.status,
    }


class GetChatSurfaceSessionByIdempotencyController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        result = await self._use_case.execute(
            GetChatSurfaceSessionByIdempotencyInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                idempotency_key=str(body["idempotency_key"]),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": _binding_payload(result) if result is not None else None,
            },
        )


class GetChatSurfaceSessionBindingController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetChatSurfaceSessionBindingInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                session_id=UUID(str(request.path_params["session_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": _binding_payload(result)},
        )


class CreateChatSurfaceSessionBindingController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        result = await self._use_case.execute(
            CreateChatSurfaceSessionBindingInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                expected_project_id=UUID(str(body["expected_project_id"])),
                expected_target_type=str(body["expected_target_type"]),
                expected_target_id=UUID(str(body["expected_target_id"])),
                expected_target_release_id=UUID(
                    str(body["expected_target_release_id"])
                ),
                session_id=UUID(str(body["session_id"])),
                surface_credential_id=UUID(str(body["surface_credential_id"])),
                idempotency_key=str(body["idempotency_key"]),
                external_reference=body.get("external_reference"),
                metadata=body.get("metadata"),
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": _binding_payload(result)},
        )


class IssueChatSurfaceSessionTokenController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        result = await self._use_case.execute(
            IssueChatSurfaceSessionTokenInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                session_id=UUID(str(request.path_params["session_id"])),
                surface_credential_id=UUID(str(body["surface_credential_id"])),
                origin=str(body["origin"]),
            )
        )
        return Response(
            status_code=201,
            body={
                "success": True,
                "data": {
                    "session_id": str(result.session_id),
                    "target_release_id": str(result.target_release_id),
                    "session_token": result.token,
                    "expires_in": result.expires_in,
                },
            },
        )


class ArchiveChatSurfaceSessionBindingController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            ArchiveChatSurfaceSessionBindingInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                session_id=UUID(str(request.path_params["session_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": _binding_payload(result)},
        )


__all__ = [
    "ArchiveChatSurfaceSessionBindingController",
    "CreateChatSurfaceSessionBindingController",
    "GetChatSurfaceSessionBindingController",
    "GetChatSurfaceSessionByIdempotencyController",
    "IssueChatSurfaceSessionTokenController",
]
