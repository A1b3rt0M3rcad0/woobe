from modules.agent.application.interfaces.use_case import UseCase
import logging
from uuid import UUID

from shared.contracts.errors import NotFoundError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class GetAskJobController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            job_id = UUID(request.path_params["job_id"])
            result = await self._use_case.execute(job_id)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={
                    "success": True,
                    "message": "ok",
                    "data": result.model_dump(),
                },
            )
        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )
        except Exception as e:
            logger.exception("Failed to get ask job: %s", e)
            return OperationResult(
                outcome=OperationOutcome.FAILURE,
                body={"success": False, "message": "Internal server error", "data": None},
            )

