from modules.agent.presentation.mappers import document_to_response
from modules.agent.application.dtos import GetDocumentInput
from modules.agent.application.use_cases.knowledge_use_cases import GetDocumentUseCase
from shared.domain.errors import NotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetDocumentController(Controller):
    def __init__(self, use_case: GetDocumentUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = GetDocumentInput(document_id=request.params.get("document_id"))
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": document_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return Response(
                status_code=404,
                body={"success": False, "message": str(e), "data": None},
            )
