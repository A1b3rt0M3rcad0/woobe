from uuid import UUID

from modules.agent.application.use_cases.tools_use_cases import GetToolUsageImpactUseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetToolUsageImpactController(Controller):
    def __init__(self, use_case: GetToolUsageImpactUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        tool_id = UUID(request.path_params["tool_id"])
        impact = await self._use_case.execute(tool_id)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": impact.model_dump(mode="json"),
            },
        )
