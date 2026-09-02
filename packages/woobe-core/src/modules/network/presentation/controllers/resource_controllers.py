from uuid import UUID

from modules.network.application.dtos.resources import (
    CreateProjectNetworkInput,
    GetProjectNetworkInput,
    ListProjectNetworksInput,
    UpdateProjectNetworkInput,
)
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListProjectNetworksController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            ListProjectNetworksInput(project_id=project_id)
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [item.model_dump() for item in result],
            },
        )


class CreateProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            CreateProjectNetworkInput(
                project_id=project_id,
                name=body.get("name", ""),
                description=body.get("description", ""),
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": result.model_dump()},
        )


class GetProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            GetProjectNetworkInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump()},
        )


class UpdateProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            UpdateProjectNetworkInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                name=body.get("name"),
                description=body.get("description"),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump()},
        )
