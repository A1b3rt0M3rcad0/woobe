from modules.agent.application.use_cases.runtime_use_cases import CreateSessionUseCase
from modules.agent.application.dtos import CreateSessionInput
from modules.agent.presentation.schemas import SessionResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateSessionController(Controller):
    def __init__(self, use_case: CreateSessionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateSessionInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": SessionResponse(**result.model_dump()).model_dump()},
        )
