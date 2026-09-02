from modules.identity.application.dtos import CreateUserInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import UserResponse
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CreateUserController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateUserInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": UserResponse(**result.model_dump()).model_dump(),
            },
        )
