from modules.identity.application.dtos import ListMembersInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import MemberResponse
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListMembersController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(ListMembersInput(workspace_id=workspace_id))
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [
                    MemberResponse(
                        id=member.id,
                        user_id=member.user_id,
                        workspace_id=member.workspace_id,
                        role=member.role.value if hasattr(member.role, "value") else member.role,
                        status=member.status.value if hasattr(member.status, "value") else member.status,
                    ).model_dump()
                    for member in result
                ],
            },
        )
