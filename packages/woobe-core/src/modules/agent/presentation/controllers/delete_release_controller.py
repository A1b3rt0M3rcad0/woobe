from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.domain.errors import ReleaseNotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class DeleteReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        release_id = request.path_params["release_id"]
        try:
            await self._use_case.execute(UUID(release_id))
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={"success": True, "message": "Release deleted"},
            )
        except ReleaseNotFoundError:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": "Release not found"},
            )

