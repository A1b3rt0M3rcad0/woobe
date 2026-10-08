from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetVectorSnapshotInput,
)
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import OperationOutcome, OperationResult


class ImportedVectorController:
    def __init__(self, use_case: UseCase, *, verify=False):
        self._use_case, self._verify = use_case, verify

    async def handle(self, request):
        dto = GetVectorSnapshotInput if self._verify else CreateVectorSnapshotInput
        result = await self._use_case.execute(dto.model_validate(request.body))
        data = result if isinstance(result, dict) else result.model_dump(mode="json")
        return OperationResult(
            outcome=OperationOutcome.SUCCESS
            if self._verify
            else OperationOutcome.CREATED,
            body={"success": True, "data": data},
        )
