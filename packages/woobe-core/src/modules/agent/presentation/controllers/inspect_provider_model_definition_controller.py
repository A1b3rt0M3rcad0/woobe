from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from shared.presentation.contracts import OperationRequest, OperationResult


class InspectProviderModelDefinitionController:
    def __init__(self, use_case):
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        definition = await self._use_case.execute(
            CreateProviderModelInput.model_validate(request.body)
        )
        return OperationResult(body={"success": True, "data": definition})
