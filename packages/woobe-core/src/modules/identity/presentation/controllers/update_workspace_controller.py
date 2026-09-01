from uuid import UUID
from modules.identity.application.use_cases import UpdateWorkspaceUseCase
from modules.identity.application.dtos import UpdateWorkspaceInput
from modules.identity.presentation.schemas import WorkspaceResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UpdateWorkspaceController(Controller):
    def __init__(self, use_case: UpdateWorkspaceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = UUID(request.path_params.get("workspace_id"))
        input_dto = UpdateWorkspaceInput(**request.body)
        result = await self._use_case.execute(workspace_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": WorkspaceResponse(**result.model_dump()).model_dump()},
        )
