from modules.agent.presentation.mappers import collection_to_response
from modules.agent.application.dtos.knowledge_dtos import ListCollectionsInput
from modules.agent.application.use_cases.knowledge_use_cases import ListCollectionsUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListCollectionsController(Controller):
    def __init__(self, use_case: ListCollectionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = ListCollectionsInput(project_id=request.query.get("project_id"))
        results = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [collection_to_response(c).model_dump() for c in results],
            },
        )
