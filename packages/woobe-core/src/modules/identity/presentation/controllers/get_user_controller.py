from modules.identity.application.use_cases import GetUserUseCase
from modules.identity.application.dtos import GetUserInput
from modules.identity.presentation.schemas import UserResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetUserController(Controller):
    def __init__(self, use_case: GetUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        user_id = request.path_params["user_id"]
        result = await self._use_case.execute(GetUserInput(user_id=user_id))
        if result is None:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": "User not found", "data": None},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": UserResponse(**result.model_dump()).model_dump()},
        )

