from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.presentation.mappers import prompt_to_response
from modules.agent.domain.errors import PromptNotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetPromptVersionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        version_id = request.path_params["version_id"]
        try:
            result = await self._use_case.execute(UUID(version_id))
        except PromptNotFoundError:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": "Prompt version not found"},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "data": prompt_to_response(result).model_dump()},
        )

