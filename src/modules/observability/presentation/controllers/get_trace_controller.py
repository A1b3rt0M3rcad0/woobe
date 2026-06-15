from modules.observability.application.use_cases import GetTraceUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.infra.errors import NotFoundError


class GetTraceController(Controller):
    def __init__(self, use_case: GetTraceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        trace_id = request.path_params["trace_id"]
        try:
            result = await self._use_case.execute(trace_id)
        except NotFoundError as e:
            return Response(status_code=404, body={"success": False, "message": str(e), "data": None})
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
