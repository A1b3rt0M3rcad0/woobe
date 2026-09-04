from modules.identity.application.use_cases import ListMembersUseCase
from modules.identity.application.dtos import ListMembersInput
from modules.identity.presentation.schemas import MemberResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListMembersController(Controller):
    def __init__(self, use_case: ListMembersUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(ListMembersInput(workspace_id=workspace_id))
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [MemberResponse(
                    id=m.id,
                    user_id=m.user_id,
                    workspace_id=m.workspace_id,
                    role=m.role.value if hasattr(m.role, "value") else m.role,
                    status=m.status.value if hasattr(m.status, "value") else m.status,
                ).model_dump() for m in result],
            },
        )

