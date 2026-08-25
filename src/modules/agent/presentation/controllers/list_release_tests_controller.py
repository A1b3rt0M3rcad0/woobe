from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import list_release_tests_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListReleaseTestsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        release_id = request.path_params["release_id"]
        result = await self._use_case.execute(release_id)
        items = [list_release_tests_to_response(t).model_dump() for t in result]
        return Response(
            status_code=200,
            body={"success": True, "data": items},
        )
