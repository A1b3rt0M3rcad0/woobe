from modules.knowledge.presentation.mappers import document_to_response
from modules.knowledge.service.dtos import ListDocumentsInput
from modules.knowledge.service.use_cases import ListDocumentsUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListDocumentsController(Controller):
    def __init__(self, use_case: ListDocumentsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = request.query_params.get("project_id")
        collection_id = request.query_params.get("collection_id")
        if not project_id and not collection_id:
            return Response(
                status_code=200,
                body={"success": True, "message": "ok", "data": []},
            )
        input_dto = ListDocumentsInput(
            project_id=project_id,
            collection_id=collection_id,
        )
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [document_to_response(d).model_dump() for d in result],
            },
        )
