from uuid import UUID

from modules.network.application.dtos.execution import AcceptNetworkExecutionInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class AcceptNetworkExecutionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            AcceptNetworkExecutionInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                network_session_id=UUID(str(body["network_session_id"])),
                message=str(body.get("message") or ""),
                idempotency_key=body.get("idempotency_key"),
                expected_draft_revision=body.get("expected_draft_revision"),
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
