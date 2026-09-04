from modules.core.application.dtos import RotateApiKeyInput
from modules.core.application.use_cases import RotateApiKeyUseCase
from modules.core.presentation.schemas import CreatedApiKeyResponse
from shared.infra.errors import AuthenticationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class RotateApiKeyController(Controller):
    def __init__(self, use_case: RotateApiKeyUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthenticationError("User authentication required")
        body = dict(request.body or {})
        body.update(
            {
                "project_id": request.path_params["project_id"],
                "api_key_id": request.path_params["api_key_id"],
                "rotated_by_user_id": principal.user_id,
            }
        )
        result = await self._use_case.execute(RotateApiKeyInput(**body))
        response_data = CreatedApiKeyResponse(
            id=result.id,
            credential_id=result.credential_id,
            project_id=result.project_id,
            name=result.name,
            description=result.description,
            key=result.key,
            key_prefix=result.key_prefix,
            scopes=result.scopes,
            kind=result.kind.value,
            agent_id=result.agent_id,
            target_type=result.target_type.value if result.target_type else None,
            target_id=result.target_id,
            environment=result.environment.value if result.environment else None,
            interfaces=result.interfaces,
            status=result.status.value,
            expires_at=result.expires_at,
            created_at=result.created_at,
            rotated_from_id=result.rotated_from_id,
        )
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={
                "success": True,
                "message": "rotated",
                "data": response_data.model_dump(),
            },
        )

