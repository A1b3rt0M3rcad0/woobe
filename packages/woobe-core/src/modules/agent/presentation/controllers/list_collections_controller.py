from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import collection_to_response
from modules.agent.application.dtos import ListCollectionsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListCollectionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = ListCollectionsInput(project_id=request.query.get("project_id"))
        results = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [collection_to_response(c).model_dump() for c in results],
            },
        )

