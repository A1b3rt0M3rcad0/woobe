from modules.identity.service.use_cases import ListInvitesUseCase
from modules.identity.service.dtos import ListInvitesInput
from modules.identity.presentation.schemas import InviteResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListInvitesController(Controller):
    def __init__(self, use_case: ListInvitesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        org_id = request.path_params["org_id"]
        result = await self._use_case.execute(ListInvitesInput(organization_id=org_id))
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [InviteResponse(
                    id=i.id,
                    organization_id=i.organization_id,
                    email=i.email,
                    role=i.role.value if hasattr(i.role, "value") else i.role,
                    status=i.status.value if hasattr(i.status, "value") else i.status,
                    expires_at=i.expires_at,
                    created_at=i.created_at,
                ).model_dump() for i in result],
            },
        )
