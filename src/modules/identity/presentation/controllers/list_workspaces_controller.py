from modules.identity.application.use_cases import ListWorkspacesUseCase
from modules.identity.application.dtos import ListWorkspacesInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListWorkspacesController(Controller):
    def __init__(self, use_case: ListWorkspacesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(ListWorkspacesInput())
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
