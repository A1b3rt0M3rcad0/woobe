from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import upload_document_output_to_response
from modules.agent.application.dtos import UploadDocumentInput
from shared.contracts.errors import NotFoundError, ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UploadDocumentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = UploadDocumentInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=201,
                body={
                    "success": True,
                    "message": "created",
                    "data": upload_document_output_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return Response(
                status_code=404,
                body={"success": False, "message": str(e), "data": None},
            )
        except ValidationError as e:
            return Response(
                status_code=422,
                body={"success": False, "message": str(e), "data": None},
            )
