from uuid import UUID
from modules.identity.service.use_cases import UpdateOrganizationUseCase
from modules.identity.service.dtos import UpdateOrganizationInput
from modules.identity.presentation.schemas import OrganizationResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UpdateOrganizationController(Controller):
    def __init__(self, use_case: UpdateOrganizationUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        org_id = UUID(request.path_params.get("org_id"))
        input_dto = UpdateOrganizationInput(**request.body)
        result = await self._use_case.execute(org_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": OrganizationResponse(**result.model_dump()).model_dump()},
        )
