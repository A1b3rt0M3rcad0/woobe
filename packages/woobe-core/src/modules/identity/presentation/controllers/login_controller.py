from modules.identity.application.use_cases import LoginUseCase
from modules.identity.application.dtos import LoginInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from modules.identity.domain.errors import InvalidCredentialsError


class LoginController(Controller):
    def __init__(self, use_case: LoginUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = LoginInput(**request.body)
        try:
            result = await self._use_case.execute(input_dto)
        except InvalidCredentialsError:
            return OperationResult(
                outcome=OperationOutcome.UNAUTHENTICATED,
                body={"success": False, "message": "Invalid credentials", "data": None},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )

