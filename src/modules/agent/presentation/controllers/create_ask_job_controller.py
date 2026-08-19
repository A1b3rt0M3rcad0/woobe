from modules.agent.application.interfaces.use_case import UseCase
import logging

from modules.agent.application.dtos import CreateAskJobInput
from shared.contracts.errors import ValidationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class CreateAskJobController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = CreateAskJobInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=201,
                body={
                    "success": True,
                    "message": "Ask job created",
                    "data": result.model_dump(),
                },
            )
        except ValidationError as e:
            return Response(
                status_code=400,
                body={"success": False, "message": str(e), "data": None},
            )
        except Exception as e:
            logger.exception("Failed to create ask job: %s", e)
            return Response(
                status_code=500,
                body={"success": False, "message": "Internal server error", "data": None},
            )
