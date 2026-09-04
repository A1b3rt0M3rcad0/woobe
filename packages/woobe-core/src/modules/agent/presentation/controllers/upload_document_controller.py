from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import upload_document_output_to_response
from modules.agent.application.dtos import UploadDocumentInput
from shared.contracts.errors import NotFoundError, ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class UploadDocumentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = UploadDocumentInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.CREATED,
                body={
                    "success": True,
                    "message": "created",
                    "data": upload_document_output_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )
        except ValidationError as e:
            return OperationResult(
                outcome=OperationOutcome.UNPROCESSABLE,
                body={"success": False, "message": str(e), "data": None},
            )

