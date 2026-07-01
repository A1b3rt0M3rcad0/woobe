from modules.agent.application.dtos import ListProviderModelsInput
from modules.agent.application.use_cases import ListProviderModelsUseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListProviderModelsController(Controller):
    def __init__(self, use_case: ListProviderModelsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = ListProviderModelsInput(
            project_id=request.query_params.get("project_id"),
            provider_credential_id=request.query_params.get("provider_credential_id"),
        )
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [item.model_dump() for item in result]},
        )
