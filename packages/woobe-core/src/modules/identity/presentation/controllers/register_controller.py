from modules.identity.application.use_cases import RegisterUseCase
from modules.identity.application.dtos import RegisterInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class RegisterController(Controller):
    def __init__(self, use_case: RegisterUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = RegisterInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": result.model_dump()},
        )
