from modules.agent.application.interfaces.use_case import UseCase
from typing import cast
from uuid import UUID

from modules.agent.presentation.mappers import document_to_response
from modules.agent.application.dtos import GetDocumentInput
from shared.contracts.errors import NotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetDocumentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = GetDocumentInput(document_id=cast(UUID, request.params.get("document_id")))
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={
                    "success": True,
                    "message": "ok",
                    "data": document_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )

