from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import CreateProviderCredentialInput
from modules.agent.presentation.schemas import ProviderCredentialResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class CreateProviderCredentialController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateProviderCredentialInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": ProviderCredentialResponse(**result.model_dump()).model_dump()},
        )

