from modules.core.application.interfaces.use_case import UseCase
from modules.core.application.dtos import RevokeApiKeyInput
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class RevokeApiKeyController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthenticationError("User authentication required")
        result = await self._use_case.execute(
            RevokeApiKeyInput(
                project_id=request.path_params["project_id"],
                api_key_id=request.path_params["api_key_id"],
                revoked_by_user_id=principal.user_id,
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "revoked",
                "data": result.model_dump(),
            },
        )
