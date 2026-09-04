from modules.identity.application.use_cases import AddMemberToWorkspaceUseCase
from modules.identity.application.dtos import AddMemberInput
from modules.identity.presentation.schemas import MemberResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class AddMemberController(Controller):
    def __init__(self, use_case: AddMemberToWorkspaceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        body = dict(request.body)
        body["workspace_id"] = request.path_params.get("workspace_id")
        input_dto = AddMemberInput(**body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={
                "success": True,
                "message": "created",
                "data": MemberResponse(
                    id=result.id,
                    user_id=result.user_id,
                    workspace_id=result.workspace_id,
                    role=result.role.value if hasattr(result.role, "value") else result.role,
                    status=result.status.value if hasattr(result.status, "value") else result.status,
                ).model_dump(),
            },
        )

