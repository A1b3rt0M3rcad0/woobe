from uuid import UUID

from modules.agent.application.dtos.ai_dtos import ExecuteReleaseTestInput
from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import release_test_to_response
from shared.presentation.contracts import OperationResult
from shared.contracts.errors import ValidationError


class ExecuteReleaseTestController:
    def __init__(self, use_case: UseCase):
        self._use_case = use_case

    async def handle(self, request):
        body = ExecuteReleaseTestInput(**request.body)
        if body.agent_id != UUID(request.path_params["agent_id"]):
            raise ValidationError("Test target differs from the Agent path")
        result = await self._use_case.execute(body, request.principal)
        return OperationResult(
            body={
                "success": True,
                "data": release_test_to_response(result).model_dump(),
            }
        )
