from uuid import UUID

from modules.network.application.dtos.public_runtime import SubmitPublicNetworkRunInput
from modules.network.application.interfaces.use_case import UseCase
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import ProjectApiPrincipal


class SubmitPublicNetworkRunController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    @staticmethod
    def _principal(request: Request) -> ProjectApiPrincipal:
        principal = request.principal
        if not isinstance(principal, ProjectApiPrincipal):
            raise AuthenticationError("Runtime Key authentication required")
        if principal.kind != "runtime":
            raise AuthorizationError("A Runtime Key is required for this endpoint")
        if (
            principal.target_type != "network"
            or principal.target_id is None
            or principal.environment is None
        ):
            raise AuthorizationError("Network Runtime Key binding is incomplete")
        if principal.environment == "draft":
            raise AuthorizationError("Runtime Keys cannot execute a Network Draft")
        return principal

    async def handle(self, request: Request) -> Response:
        principal = self._principal(request)
        body = dict(request.body or {})
        idempotency_key = body.get("idempotency_key") or request.headers.get(
            "idempotency-key"
        ) or request.headers.get("Idempotency-Key")
        result = await self._use_case.execute(
            SubmitPublicNetworkRunInput(
                project_id=principal.project_id,
                network_id=UUID(str(principal.target_id)),
                environment=principal.environment,
                message=str(body.get("message") or ""),
                session_id=body.get("session_id"),
                tenant_id=body.get("tenant_id"),
                user_id=body.get("user_id"),
                idempotency_key=idempotency_key,
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
