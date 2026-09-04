from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos.tools_dtos import ListSecretsInput
from modules.agent.presentation.schemas import SecretResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListSecretsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.query_params.get("project_id")
        input_dto = ListSecretsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [
                    SecretResponse(
                        **{k: v for k, v in vars(r).items() if k != "encrypted_value"}
                    ).model_dump()
                    for r in result
                ],
            },
        )

