from uuid import UUID

from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.domain.errors import DocumentNotFoundError
from shared.contracts.errors import ConflictError
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class DeleteDocumentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, document_id: UUID) -> Response:
        try:
            await self._use_case.execute(document_id)
        except DocumentNotFoundError:
            return Response(
                status_code=404,
                body={
                    "success": False,
                    "message": "Document not found",
                    "data": None,
                },
            )
        except ConflictError as exc:
            return Response(
                status_code=409,
                body={"success": False, "message": str(exc), "data": None},
            )

        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "Document deleted",
                "data": None,
            },
        )
