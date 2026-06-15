from modules.identity.application.use_cases import ListMembersUseCase
from modules.identity.application.dtos import ListMembersInput
from modules.identity.presentation.schemas import MemberResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListMembersController(Controller):
    def __init__(self, use_case: ListMembersUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        org_id = request.path_params["org_id"]
        result = await self._use_case.execute(ListMembersInput(organization_id=org_id))
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [MemberResponse(
                    id=m.id,
                    user_id=m.user_id,
                    organization_id=m.organization_id,
                    role=m.role.value if hasattr(m.role, "value") else m.role,
                    status=m.status.value if hasattr(m.status, "value") else m.status,
                ).model_dump() for m in result],
            },
        )
