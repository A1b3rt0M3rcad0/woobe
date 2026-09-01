from typing import Any

from modules.agent.application.dtos import UploadDocumentFileInput
from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import upload_document_output_to_response
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class UploadDocumentFileController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(
        self,
        request: tuple[UploadDocumentFileInput, Any],
    ) -> Response:
        input_dto, upload = request
        try:
            result = await self._use_case.execute(input_dto, upload)
        except ConflictError as exc:
            return Response(
                status_code=409,
                body={"success": False, "message": str(exc), "data": None},
            )
        except NotFoundError as exc:
            return Response(
                status_code=404,
                body={"success": False, "message": str(exc), "data": None},
            )
        except ValidationError as exc:
            return Response(
                status_code=400,
                body={"success": False, "message": str(exc), "data": None},
            )

        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": upload_document_output_to_response(result).model_dump(),
            },
        )
