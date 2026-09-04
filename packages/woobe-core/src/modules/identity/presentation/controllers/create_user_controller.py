from modules.identity.application.use_cases import CreateUserUseCase
from modules.identity.application.dtos import CreateUserInput
from modules.identity.presentation.schemas import UserResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class CreateUserController(Controller):
    def __init__(self, use_case: CreateUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateUserInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": UserResponse(**result.model_dump()).model_dump()},
        )

