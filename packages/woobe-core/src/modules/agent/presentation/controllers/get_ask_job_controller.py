from modules.agent.application.interfaces.use_case import UseCase
import logging
from uuid import UUID

from shared.contracts.errors import NotFoundError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class GetAskJobController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            job_id = UUID(request.path_params["job_id"])
            result = await self._use_case.execute(job_id)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": result.model_dump(),
                },
            )
        except NotFoundError as e:
            return Response(
                status_code=404,
                body={"success": False, "message": str(e), "data": None},
            )
        except Exception as e:
            logger.exception("Failed to get ask job: %s", e)
            return Response(
                status_code=500,
                body={"success": False, "message": "Internal server error", "data": None},
            )
