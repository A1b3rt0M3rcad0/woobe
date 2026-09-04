from uuid import UUID

from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.domain.errors import DocumentNotFoundError
from shared.contracts.errors import ConflictError
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class DeleteDocumentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, document_id: UUID) -> OperationResult:
        try:
            await self._use_case.execute(document_id)
        except DocumentNotFoundError:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={
                    "success": False,
                    "message": "Document not found",
                    "data": None,
                },
            )
        except ConflictError as exc:
            return OperationResult(
                outcome=OperationOutcome.CONFLICT,
                body={"success": False, "message": str(exc), "data": None},
            )

        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "Document deleted",
                "data": None,
            },
        )

