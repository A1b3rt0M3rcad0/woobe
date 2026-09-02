from modules.observability.application.dtos import ListTracesInput
from modules.observability.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListTracesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = ListTracesInput(
            project_id=request.query_params.get("project_id"),
            agent_id=request.query_params.get("agent_id"),
            session_id=request.query_params.get("session_id"),
            network_id=request.query_params.get("network_id"),
            limit=int(request.query_params.get("limit", 100)),
            offset=int(request.query_params.get("offset", 0)),
        )
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [item.model_dump() for item in result],
            },
        )
