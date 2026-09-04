from modules.identity.application.use_cases import RegisterUseCase
from modules.identity.application.dtos import RegisterInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class RegisterController(Controller):
    def __init__(self, use_case: RegisterUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = RegisterInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": result.model_dump()},
        )

