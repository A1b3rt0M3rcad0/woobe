from modules.identity.application.use_cases import GetWorkspaceUseCase
from modules.identity.application.dtos import GetWorkspaceInput
from modules.identity.presentation.schemas import WorkspaceResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetWorkspaceController(Controller):
    def __init__(self, use_case: GetWorkspaceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(GetWorkspaceInput(workspace_id=workspace_id))
        if result is None:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": "Workspace not found", "data": None},
            )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": WorkspaceResponse(**result.model_dump()).model_dump()},
        )

