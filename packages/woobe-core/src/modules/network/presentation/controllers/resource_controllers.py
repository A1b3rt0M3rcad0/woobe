from uuid import UUID

from modules.network.application.dtos.resources import (
    CreateProjectNetworkInput,
    GetProjectNetworkInput,
    ListProjectNetworksInput,
    UpdateProjectNetworkInput,
)
from modules.network.application.interfaces.use_case import UseCase
from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


def _project_id(request: Request) -> UUID:
    return UUID(str(request.path_params["project_id"]))


def _authorize_project(request: Request, project_id: UUID) -> None:
    principal = request.principal
    if isinstance(principal, ProjectApiPrincipal):
        if principal.project_id != project_id:
            raise AuthorizationError("Runtime key does not belong to this Project")
        return
    if isinstance(principal, AuthenticatedPrincipal):
        return
    raise AuthorizationError("Authentication required")


class ListProjectNetworksController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = _project_id(request)
        _authorize_project(request, project_id)
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
        project_id = _project_id(request)
        _authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            CreateProjectNetworkInput(project_id=project_id, **body)
        )
        return Response(
            status_code=201,
            body={"success": True, "data": result.model_dump()},
        )


class GetProjectNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = _project_id(request)
        _authorize_project(request, project_id)
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
        project_id = _project_id(request)
        _authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            UpdateProjectNetworkInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                **body,
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump()},
        )
