from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos import ListProviderModelsInput
from modules.agent.application.dtos.model_discovery_dtos import ListAvailableProviderModelsInput
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListProviderModelsController(Controller):
    def __init__(
        self,
        use_case: UseCase,
        discovery_use_case: UseCase | None = None,
    ) -> None:
        self._use_case = use_case
        self._discovery_use_case = discovery_use_case

    async def handle(self, request: Request) -> Response:
        available_for_credential_id = request.query_params.get("available_for_credential_id")
        if available_for_credential_id:
            if self._discovery_use_case is None:
                return Response(
                    status_code=400,
                    body={"success": False, "message": "Model discovery is not configured", "data": None},
                )
            result = await self._discovery_use_case.execute(
                ListAvailableProviderModelsInput(
                    credential_id=UUID(available_for_credential_id),
                    project_id=request.query_params.get("project_id"),
                    capability=request.query_params.get("capability"),
                )
            )
            return Response(
                status_code=200,
                body={"success": True, "message": "ok", "data": [item.model_dump() for item in result]},
            )

        input_dto = ListProviderModelsInput(
            project_id=request.query_params.get("project_id"),
            provider_credential_id=request.query_params.get("provider_credential_id"),
        )
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [item.model_dump() for item in result]},
        )
