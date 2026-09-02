from uuid import UUID

from modules.identity.application.dtos import GetUserInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import UserResponse
from shared.contracts.errors import AuthenticationError, NotFoundError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class GetUserController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        if not isinstance(request.principal, AuthenticatedPrincipal):
            raise AuthenticationError("Authentication required")
        user_id = UUID(str(request.path_params["user_id"]))
        if request.principal.user_id != user_id:
            raise NotFoundError("User not found")
        result = await self._use_case.execute(GetUserInput(user_id=user_id))
        if result is None:
            return Response(
                status_code=404,
                body={"success": False, "message": "User not found", "data": None},
            )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": UserResponse(**result.model_dump()).model_dump(),
            },
        )
