from modules.agent.application.interfaces.use_case import UseCase
from typing import cast
from uuid import UUID

from modules.agent.presentation.mappers import agent_collection_output_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListAgentCollectionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        agent_id = cast(UUID, request.params.get("agent_id") or request.query.get("agent_id"))
        results = await self._use_case.execute(agent_id)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [agent_collection_output_to_response(r).model_dump() for r in results],
            },
        )

