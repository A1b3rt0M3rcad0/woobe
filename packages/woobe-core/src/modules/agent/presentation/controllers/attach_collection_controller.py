from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import attach_collection_output_to_response
from modules.agent.application.dtos import AttachCollectionInput
from shared.contracts.errors import ConflictError, ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class AttachCollectionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = AttachCollectionInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.CREATED,
                body={
                    "success": True,
                    "message": "created",
                    "data": attach_collection_output_to_response(result).model_dump(),
                },
            )
        except ConflictError as e:
            return OperationResult(
                outcome=OperationOutcome.CONFLICT,
                body={"success": False, "message": str(e), "data": None},
            )
        except ValidationError as e:
            return OperationResult(
                outcome=OperationOutcome.UNPROCESSABLE,
                body={"success": False, "message": str(e), "data": None},
            )

