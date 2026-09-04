from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import UpdateProviderCredentialInput
from modules.agent.presentation.mappers import credential_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class UpdateProviderCredentialController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        credential_id = request.path_params["credential_id"]
        raw = {k: v for k, v in request.body.items() if v is not None}
        input_dto = UpdateProviderCredentialInput(**raw)
        result = await self._use_case.execute(credential_id, input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": credential_to_response(result).model_dump()},
        )

