from modules.agent.application.dtos.imported_agent_verification_dtos import (
    VerifyImportedAgentInput,
)
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)


class VerifyImportedAgentController:
    def __init__(self, use_case: UseCase):
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        data = await self._use_case.execute(
            VerifyImportedAgentInput.model_validate(request.body)
        )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data}
        )
