from modules.identity.application.use_cases import GetUserUseCase
from modules.identity.application.dtos import GetUserInput
from modules.identity.presentation.schemas import UserResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetUserController(Controller):
    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        user_id = request.path_params["user_id"]
        result = await self._use_case.execute(GetUserInput(user_id=user_id))
        if result is None:
            return Response(
                status_code=404,
                body={"success": False, "message": "User not found", "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": UserResponse(**result.model_dump()).model_dump()},
        )
