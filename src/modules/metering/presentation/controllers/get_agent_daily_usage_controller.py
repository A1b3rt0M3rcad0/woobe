from modules.metering.application.use_cases import GetAgentDailyUsageUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetAgentDailyUsageController(Controller):
    def __init__(self, use_case: GetAgentDailyUsageUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        result = await self._use_case.execute(agent_id, limit=limit, offset=offset)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
