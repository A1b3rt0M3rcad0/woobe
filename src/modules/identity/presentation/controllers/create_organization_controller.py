from modules.identity.application.use_cases import CreateOrganizationUseCase
from modules.identity.application.dtos import CreateOrganizationInput
from modules.identity.presentation.schemas import OrganizationResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateOrganizationController(Controller):
    def __init__(self, use_case: CreateOrganizationUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateOrganizationInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": OrganizationResponse(**result.model_dump()).model_dump()},
        )
