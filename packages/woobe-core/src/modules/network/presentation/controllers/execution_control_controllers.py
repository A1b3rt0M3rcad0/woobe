from uuid import UUID

from modules.network.application.dtos.execution import CancelNetworkExecutionInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CancelNetworkExecutionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            CancelNetworkExecutionInput(
                execution_id=UUID(str(request.path_params["execution_id"])),
                project_id=project_id,
            )
        )
        return Response(
            status_code=202,
            body={
                "success": True,
                "data": {
                    "execution_id": str(result.id),
                    "run_id": str(result.id),
                    "status": result.status,
                },
            },
        )
