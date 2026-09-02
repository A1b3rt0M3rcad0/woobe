from modules.observability.application.dtos import CreateTraceInput
from modules.observability.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CreateTraceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateTraceInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": {"trace_id": str(result.trace_id)},
            },
        )
