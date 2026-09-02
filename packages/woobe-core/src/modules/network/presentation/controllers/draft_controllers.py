from uuid import UUID

from modules.network.application.dtos.draft import SaveNetworkDraftInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class SaveNetworkDraftController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            SaveNetworkDraftInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                expected_revision=body.get("expected_revision", 0),
                name=body.get("name", ""),
                description=body.get("description", ""),
                definition=body.get("definition", {}),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": result.model_dump(),
                "revision": result.draft_revision,
            },
        )
