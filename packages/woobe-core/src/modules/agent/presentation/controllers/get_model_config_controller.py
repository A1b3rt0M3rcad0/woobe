from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.presentation.mappers import model_config_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetModelConfigController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        config_id = request.path_params["config_id"]
        result = await self._use_case.execute(UUID(config_id))
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "data": model_config_to_response(result).model_dump()},
        )

