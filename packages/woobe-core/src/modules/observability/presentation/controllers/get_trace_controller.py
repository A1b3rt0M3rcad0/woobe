from modules.observability.application.interfaces.use_case import UseCase
from modules.observability.domain.errors import TraceNotFoundError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetTraceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        trace_id = request.path_params["trace_id"]
        try:
            result = await self._use_case.execute(trace_id)
        except TraceNotFoundError as exc:
            return Response(
                status_code=404,
                body={"success": False, "message": str(exc), "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
