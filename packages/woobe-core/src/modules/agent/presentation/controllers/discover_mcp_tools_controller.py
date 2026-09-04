from modules.agent.application.dtos.mcp_discovery_dtos import McpDiscoverInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class DiscoverMcpToolsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = McpDiscoverInput(**request.body)
        result = await self._use_case.execute(input_dto)
        if result.error:
            return OperationResult(
                outcome=OperationOutcome.UPSTREAM_FAILURE,
                body={
                    "success": False,
                    "message": result.error,
                    "data": result.model_dump(),
                },
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
