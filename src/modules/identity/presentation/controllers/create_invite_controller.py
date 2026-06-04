from uuid import UUID
from modules.identity.service.use_cases import InviteUserUseCase
from modules.identity.service.dtos import InviteUserInput
from modules.identity.presentation.schemas import InviteResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateInviteController(Controller):
    def __init__(self, use_case: InviteUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body)
        body["organization_id"] = UUID(request.path_params.get("org_id"))
        body["invited_by_user_id"] = UUID("00000000-0000-0000-0000-000000000001")
        input_dto = InviteUserInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": InviteResponse(
                    id=result.id,
                    organization_id=result.organization_id,
                    email=result.email,
                    role=result.role.value if hasattr(result.role, "value") else result.role,
                    status=result.status.value if hasattr(result.status, "value") else result.status,
                    expires_at=result.expires_at,
                    created_at=result.created_at,
                ).model_dump(),
            },
        )
