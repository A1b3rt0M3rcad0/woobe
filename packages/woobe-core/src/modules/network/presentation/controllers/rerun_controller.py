from uuid import UUID

from modules.network.application.dtos.rerun import RerunNetworkExecutionInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class RerunNetworkExecutionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            RerunNetworkExecutionInput(
                execution_id=UUID(str(request.path_params["execution_id"])),
                project_id=project_id,
                idempotency_key=request.headers.get("idempotency-key"),
            )
        )
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "Network Run rerun accepted",
                "data": result.model_dump(),
            },
        )
