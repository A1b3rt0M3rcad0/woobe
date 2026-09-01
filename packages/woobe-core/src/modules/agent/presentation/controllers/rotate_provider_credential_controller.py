from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos.provider_credential_rotation_dtos import (
    RotateProviderCredentialInput,
)
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class RotateProviderCredentialController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthenticationError("User authentication required")

        body = dict(request.body or {})
        body["rotated_by_user_id"] = principal.user_id
        result = await self._use_case.execute(
            UUID(request.path_params["credential_id"]),
            RotateProviderCredentialInput(**body),
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "rotated",
                "data": {
                    "id": str(result.id),
                    "project_id": str(result.project_id),
                    "provider": getattr(result.provider, "value", result.provider),
                    "name": result.name,
                    "status": getattr(result.status, "value", result.status),
                    "created_at": result.created_at,
                    "last_validated_at": result.last_validated_at,
                    "updated_at": result.updated_at,
                    "metadata": result.metadata,
                },
            },
        )
