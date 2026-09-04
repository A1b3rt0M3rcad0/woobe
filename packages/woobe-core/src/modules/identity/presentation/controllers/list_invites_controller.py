from modules.identity.application.use_cases import ListInvitesUseCase
from modules.identity.application.dtos import ListInvitesInput
from modules.identity.presentation.schemas import InviteResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListInvitesController(Controller):
    def __init__(self, use_case: ListInvitesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(ListInvitesInput(workspace_id=workspace_id))
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": [InviteResponse(
                    id=i.id,
                    workspace_id=i.workspace_id,
                    email=i.email,
                    role=i.role.value if hasattr(i.role, "value") else i.role,
                    status=i.status.value if hasattr(i.status, "value") else i.status,
                    expires_at=i.expires_at,
                    created_at=i.created_at,
                ).model_dump() for i in result],
            },
        )

