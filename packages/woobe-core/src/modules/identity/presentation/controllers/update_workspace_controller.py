from uuid import UUID

from modules.identity.application.dtos import UpdateWorkspaceInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.schemas import WorkspaceResponse
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class UpdateWorkspaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        if not isinstance(request.principal, AuthenticatedPrincipal):
            raise AuthenticationError("Authentication required")
        workspace_id = UUID(str(request.path_params.get("workspace_id")))
        input_dto = UpdateWorkspaceInput(**request.body)
        result = await self._use_case.execute(
            request.principal.user_id,
            workspace_id,
            input_dto,
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": WorkspaceResponse(**result.model_dump()).model_dump(),
            },
        )
