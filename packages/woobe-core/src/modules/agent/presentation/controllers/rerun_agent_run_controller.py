from __future__ import annotations

import logging
from uuid import UUID

from modules.agent.application.interfaces.agent_run_rerun import AgentRunRerunExecutor
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class RerunAgentRunController(Controller):
    def __init__(self, use_case: AgentRunRerunExecutor) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            run_id = UUID(request.path_params["run_id"])
            project_id = UUID(str(request.query_params["project_id"]))
            result = await self._use_case.execute(run_id=run_id, project_id=project_id)
            return OperationResult(
                outcome=OperationOutcome.CREATED,
                body={
                    "success": True,
                    "message": "Agent Run rerun accepted",
                    "data": result.model_dump(mode="json"),
                },
            )
        except NotFoundError as exc:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(exc), "data": None},
            )
        except (ConflictError, ValidationError, KeyError, ValueError) as exc:
            return OperationResult(
                outcome=OperationOutcome.CONFLICT,
                body={"success": False, "message": str(exc), "data": None},
            )
        except Exception as exc:
            logger.exception("Failed to rerun Agent Run: %s", exc)
            return OperationResult(
                outcome=OperationOutcome.FAILURE,
                body={
                    "success": False,
                    "message": "Internal server error",
                    "data": None,
                },
            )

