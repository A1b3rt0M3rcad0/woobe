from uuid import UUID

from modules.core.application.dtos.chat_surface_credential import (
    GetChatSurfaceCredentialInput,
)
from modules.core.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetChatSurfaceCredentialController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetChatSurfaceCredentialInput(
                credential_id=UUID(str(request.path_params["credential_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": result.model_dump(mode="json") if result is not None else None,
            },
        )
