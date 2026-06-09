from uuid import UUID
from modules.ai.service.use_cases import GetModelConfigUseCase
from modules.ai.presentation.mappers import model_config_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetModelConfigController(Controller):
    def __init__(self, use_case: GetModelConfigUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        config_id = request.path_params["config_id"]
        result = await self._use_case.execute(UUID(config_id))
        return Response(
            status_code=200,
            body={"success": True, "data": model_config_to_response(result).model_dump()},
        )
