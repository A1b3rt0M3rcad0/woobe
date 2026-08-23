from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import ListProviderCredentialsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListProviderCredentialsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = request.query_params.get("project_id")
        input_dto = ListProviderCredentialsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
