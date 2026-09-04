from uuid import UUID

from modules.identity.application.use_cases import InviteUserUseCase
from modules.identity.application.dtos import InviteUserInput
from modules.identity.presentation.schemas import InviteResponse
from shared.infra.errors import AuthenticationError
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.security.principal import AuthenticatedPrincipal


class CreateInviteController(Controller):
    def __init__(self, use_case: InviteUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        if not isinstance(request.principal, AuthenticatedPrincipal):
            raise AuthenticationError("Authentication required")
        body = dict(request.body)
        body["workspace_id"] = UUID(str(request.path_params.get("workspace_id")))
        body["invited_by_user_id"] = request.principal.user_id
        input_dto = InviteUserInput(**body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={
                "success": True,
                "message": "created",
                "data": InviteResponse(
                    id=result.id,
                    workspace_id=result.workspace_id,
                    email=result.email,
                    role=result.role.value if hasattr(result.role, "value") else result.role,
                    status=result.status.value if hasattr(result.status, "value") else result.status,
                    expires_at=result.expires_at,
                    created_at=result.created_at,
                ).model_dump(),
            },
        )

