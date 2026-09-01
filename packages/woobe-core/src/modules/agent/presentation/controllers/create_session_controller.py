from modules.agent.application.dtos import CreateSessionInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateSessionController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateSessionInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": result.model_dump()},
        )
