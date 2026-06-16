from modules.agent.application.use_cases.tools_use_cases import TestToolUseCase
from modules.agent.application.dtos.tools_dtos import TestToolInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class TestToolController(Controller):
    def __init__(self, use_case: TestToolUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = TestToolInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
