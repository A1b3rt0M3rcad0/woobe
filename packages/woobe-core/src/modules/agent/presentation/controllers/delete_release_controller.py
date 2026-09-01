from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.domain.errors import ReleaseNotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DeleteReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        release_id = request.path_params["release_id"]
        try:
            await self._use_case.execute(UUID(release_id))
            return Response(
                status_code=200,
                body={"success": True, "message": "Release deleted"},
            )
        except ReleaseNotFoundError:
            return Response(
                status_code=404,
                body={"success": False, "message": "Release not found"},
            )
