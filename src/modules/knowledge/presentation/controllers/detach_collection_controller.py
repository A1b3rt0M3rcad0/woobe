from modules.knowledge.service.use_cases import DetachCollectionUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DetachCollectionController(Controller):
    def __init__(self, use_case: DetachCollectionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        link_id = request.path_params["link_id"]
        await self._use_case.execute(link_id)
        return Response(
            status_code=200,
            body={"success": True, "message": "deleted", "data": None},
        )
