from modules.identity.service.use_cases import GetOrganizationUseCase
from modules.identity.service.dtos import GetOrganizationInput
from modules.identity.presentation.schemas import OrganizationResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetOrganizationController(Controller):
    def __init__(self, use_case: GetOrganizationUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        org_id = request.path_params["org_id"]
        result = await self._use_case.execute(GetOrganizationInput(organization_id=org_id))
        if result is None:
            return Response(
                status_code=404,
                body={"success": False, "message": "Organization not found", "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": OrganizationResponse(**result.model_dump()).model_dump()},
        )
