from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.presentation.mappers import knowledge_version_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListKnowledgeVersionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        agent_id = UUID(str(request.params["agent_id"]))
        results = await self._use_case.execute(agent_id)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [knowledge_version_to_response(v).model_dump() for v in results],
            },
        )

