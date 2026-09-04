from modules.agent.application.interfaces.use_case import UseCase
from typing import cast
from uuid import UUID

from shared.contracts.errors import NotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class DetachCollectionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            link_id = cast(UUID, request.params.get("link_id"))
            await self._use_case.execute(link_id)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={"success": True, "message": "deleted", "data": None},
            )
        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )

