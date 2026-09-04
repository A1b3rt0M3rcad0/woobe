from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import chunk_output_to_response
from modules.agent.application.dtos import SearchChunksInput
from shared.contracts.errors import ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class SearchChunksController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = SearchChunksInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={
                    "success": True,
                    "message": "ok",
                    "data": [chunk_output_to_response(c).model_dump() for c in result.results],
                },
            )
        except ValidationError as e:
            return OperationResult(
                outcome=OperationOutcome.UNPROCESSABLE,
                body={"success": False, "message": str(e), "data": None},
            )

