from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import document_to_response
from modules.agent.application.dtos import ListDocumentsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListDocumentsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = ListDocumentsInput(
            project_id=request.query.get("project_id"),
            collection_id=request.query.get("collection_id"),
        )
        results = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [document_to_response(d).model_dump() for d in results],
            },
        )
