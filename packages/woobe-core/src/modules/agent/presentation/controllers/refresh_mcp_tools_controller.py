from modules.agent.application.dtos.mcp_tool_refresh_dtos import RefreshMcpProviderToolsInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class RefreshMcpToolsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(RefreshMcpProviderToolsInput(**request.body))
        except ValueError as exc:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": str(exc), "data": None},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
