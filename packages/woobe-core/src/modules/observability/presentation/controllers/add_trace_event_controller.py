from modules.observability.application.dtos import CreateTraceEventInput
from modules.observability.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class AddTraceEventController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body)
        body["trace_id"] = request.path_params["trace_id"]
        input_dto = CreateTraceEventInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": {"event_id": str(result.event_id)},
            },
        )
