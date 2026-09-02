from modules.network.application.dtos.compatibility import (
    EnsureProjectNetworkInput,
    GetLegacyProjectNetworkInput,
)
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class EnsureProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            EnsureProjectNetworkInput(
                project_id=project_id,
                name=body.get("name", "Project Network"),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump()},
        )


class GetLegacyProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            GetLegacyProjectNetworkInput(project_id=project_id)
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump()},
        )
