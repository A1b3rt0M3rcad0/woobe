from modules.agent.application.dtos.imported_mcp_dtos import CommitImportedMcpInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import OperationOutcome, OperationResult


class CommitImportedMcpController:
    def __init__(self, use_case: UseCase):
        self._use_case = use_case

    async def handle(self, request):
        result = await self._use_case.execute(
            CommitImportedMcpInput.model_validate(request.body)
        )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS, body={"success": True, "data": result}
        )
