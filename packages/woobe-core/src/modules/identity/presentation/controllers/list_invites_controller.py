from modules.identity.application.dtos import ListInvitesInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import InviteResponse
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListInvitesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(ListInvitesInput(workspace_id=workspace_id))
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [
                    InviteResponse(
                        id=item.id,
                        workspace_id=item.workspace_id,
                        email=item.email,
                        role=item.role.value if hasattr(item.role, "value") else item.role,
                        status=item.status.value if hasattr(item.status, "value") else item.status,
                        expires_at=item.expires_at,
                        created_at=item.created_at,
                    ).model_dump()
                    for item in result
                ],
            },
        )
