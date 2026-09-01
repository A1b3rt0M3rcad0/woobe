from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos.model_discovery_dtos import ListAvailableProviderModelsInput
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListAvailableProviderModelsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = ListAvailableProviderModelsInput(
            credential_id=UUID(request.path_params["credential_id"]),
            project_id=request.query_params.get("project_id"),
        )
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [item.model_dump() for item in result]},
        )
