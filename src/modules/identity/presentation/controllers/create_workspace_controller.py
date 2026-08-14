from modules.identity.application.use_cases import CreateWorkspaceUseCase
from modules.identity.application.dtos import CreateWorkspaceInput
from modules.identity.presentation.schemas import WorkspaceResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateWorkspaceController(Controller):
    def __init__(self, use_case: CreateWorkspaceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateWorkspaceInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": WorkspaceResponse(**result.model_dump()).model_dump()},
        )
