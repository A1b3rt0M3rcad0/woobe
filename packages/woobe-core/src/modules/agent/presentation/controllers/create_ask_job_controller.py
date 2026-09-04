from modules.agent.application.interfaces.use_case import UseCase
import logging

from modules.agent.application.dtos import CreateAskJobInput
from shared.contracts.errors import ValidationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class CreateAskJobController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = CreateAskJobInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.CREATED,
                body={
                    "success": True,
                    "message": "Ask job created",
                    "data": result.model_dump(),
                },
            )
        except ValidationError as e:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": str(e), "data": None},
            )
        except Exception as e:
            logger.exception("Failed to create ask job: %s", e)
            return OperationResult(
                outcome=OperationOutcome.FAILURE,
                body={"success": False, "message": "Internal server error", "data": None},
            )

