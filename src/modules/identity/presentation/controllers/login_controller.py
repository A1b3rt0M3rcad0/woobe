from modules.identity.application.use_cases import LoginUseCase
from modules.identity.application.dtos import LoginInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from modules.identity.domain.errors import InvalidCredentialsError


class LoginController(Controller):
    def __init__(self, use_case: LoginUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = LoginInput(**request.body)
        try:
            result = await self._use_case.execute(input_dto)
        except InvalidCredentialsError:
            return Response(
                status_code=401,
                body={"success": False, "message": "Invalid credentials", "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
