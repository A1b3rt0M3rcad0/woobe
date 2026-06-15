from modules.identity.application.use_cases import AddMemberToOrganizationUseCase
from modules.identity.application.dtos import AddMemberInput
from modules.identity.presentation.schemas import MemberResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class AddMemberController(Controller):
    def __init__(self, use_case: AddMemberToOrganizationUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body)
        body["organization_id"] = request.path_params.get("org_id")
        input_dto = AddMemberInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": MemberResponse(
                    id=result.id,
                    user_id=result.user_id,
                    organization_id=result.organization_id,
                    role=result.role.value if hasattr(result.role, "value") else result.role,
                    status=result.status.value if hasattr(result.status, "value") else result.status,
                ).model_dump(),
            },
        )
