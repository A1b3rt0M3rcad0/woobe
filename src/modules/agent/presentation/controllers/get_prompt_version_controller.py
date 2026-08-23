from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.presentation.mappers import prompt_to_response
from modules.agent.domain.errors import PromptNotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetPromptVersionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        version_id = request.path_params["version_id"]
        try:
            result = await self._use_case.execute(UUID(version_id))
        except PromptNotFoundError:
            return Response(
                status_code=404,
                body={"success": False, "message": "Prompt version not found"},
            )
        return Response(
            status_code=200,
            body={"success": True, "data": prompt_to_response(result).model_dump()},
        )
