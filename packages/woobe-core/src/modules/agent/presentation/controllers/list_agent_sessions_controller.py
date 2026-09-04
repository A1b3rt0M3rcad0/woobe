from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos import ListAgentSessionsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult

_VALID_ENVIRONMENTS = {"draft", "staging", "production"}


class ListAgentSessionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        agent_id = UUID(request.path_params["agent_id"])
        project_id = UUID(request.query_params["project_id"])
        raw_limit = request.query_params.get("limit", 20)
        cursor = request.query_params.get("cursor")
        environment = request.query_params.get("environment")
        if environment not in (None, "") and environment not in _VALID_ENVIRONMENTS:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": "environment must be draft, staging or production", "data": None},
            )

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        input_dto = ListAgentSessionsInput(
            project_id=project_id,
            agent_id=agent_id,
            environment=environment or None,
            cursor=cursor,
            limit=limit,
        )
        try:
            result = await self._use_case.execute(input_dto)
        except Exception as e:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": str(e), "data": None},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": {
                    "items": [r.model_dump() for r in result.items],
                    "next_cursor": result.next_cursor,
                    "has_next": result.has_next,
                },
            },
        )

