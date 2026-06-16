from modules.core.application.use_cases import ListApiKeysByProjectUseCase
from modules.core.application.dtos import ListApiKeysInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListApiKeysController(Controller):
    def __init__(self, use_case: ListApiKeysByProjectUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = request.path_params["project_id"]
        input_dto = ListApiKeysInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
