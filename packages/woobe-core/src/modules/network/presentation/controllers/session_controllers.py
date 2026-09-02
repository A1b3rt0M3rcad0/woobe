from uuid import UUID

from modules.network.application.dtos.sessions import CreateNetworkSessionInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    actor_user_id,
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import ProjectApiPrincipal


class CreateNetworkSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        principal = request.principal
        actor_id = actor_user_id(request)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            CreateNetworkSessionInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                environment=body.get("environment", "draft"),
                title=body.get("title", "New Network session"),
                tenant_id=(
                    str(principal.project_id)
                    if isinstance(principal, ProjectApiPrincipal)
                    else None
                ),
                user_id=str(actor_id) if actor_id is not None else None,
                external_session_id=body.get("external_session_id"),
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": result.model_dump()},
        )
