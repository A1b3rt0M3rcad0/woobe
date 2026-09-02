from modules.identity.application.dtos import GetWorkspaceInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import WorkspaceResponse
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetWorkspaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = request.path_params["workspace_id"]
        result = await self._use_case.execute(GetWorkspaceInput(workspace_id=workspace_id))
        if result is None:
            return Response(
                status_code=404,
                body={"success": False, "message": "Workspace not found", "data": None},
            )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": WorkspaceResponse(**result.model_dump()).model_dump(),
            },
        )
