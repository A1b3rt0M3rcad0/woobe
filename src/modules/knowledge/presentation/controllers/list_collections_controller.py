from modules.knowledge.presentation.mappers import collection_to_response
from modules.knowledge.service.dtos import ListCollectionsInput
from modules.knowledge.service.use_cases import ListCollectionsUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListCollectionsController(Controller):
    def __init__(self, use_case: ListCollectionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = request.query_params.get("project_id")
        input_dto = ListCollectionsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [collection_to_response(c).model_dump() for c in result],
            },
        )
