from uuid import UUID

from modules.knowledge.presentation.mappers import list_knowledge_versions_to_response
from modules.knowledge.service.use_cases import ListKnowledgeVersionsUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListKnowledgeVersionsController(Controller):
    def __init__(self, use_case: ListKnowledgeVersionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        result = await self._use_case.execute(agent_id)
        items = [list_knowledge_versions_to_response(v).model_dump() for v in result]
        return Response(status_code=200, body={"success": True, "data": items})
