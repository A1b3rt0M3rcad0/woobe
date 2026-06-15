from modules.agent.application.use_cases.runtime_use_cases import ListMessagesUseCase
from modules.agent.application.dtos import ListMessagesInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.infra.errors import NotFoundError


class ListMessagesController(Controller):
    def __init__(self, use_case: ListMessagesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        session_id = request.path_params["session_id"]
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 100))
        input_dto = ListMessagesInput(session_id=session_id, offset=offset, limit=limit)
        try:
            result = await self._use_case.execute(input_dto)
        except NotFoundError as e:
            return Response(status_code=404, body={"success": False, "message": str(e), "data": None})
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
