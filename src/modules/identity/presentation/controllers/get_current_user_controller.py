from modules.identity.application.use_cases import GetCurrentUserUseCase
from modules.identity.application.dtos import GetCurrentUserInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetCurrentUserController(Controller):
    def __init__(self, use_case: GetCurrentUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(GetCurrentUserInput())
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
