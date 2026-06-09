from modules.knowledge.presentation.mappers import knowledge_version_to_response
from modules.knowledge.service.dtos import CreateKnowledgeVersionInput
from modules.knowledge.service.use_cases import CreateKnowledgeVersionUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateKnowledgeVersionController(Controller):
    def __init__(self, use_case: CreateKnowledgeVersionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateKnowledgeVersionInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": knowledge_version_to_response(result).model_dump()},
        )
