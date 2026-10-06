from modules.core.application.dtos.runtime_api_key_dtos import CreateRuntimeApiKeyInput
from modules.core.application.use_cases.create_runtime_api_key_use_case import (
    CreateRuntimeApiKeyUseCase,
)
from modules.core.presentation.schemas import CreatedApiKeyResponse
from shared.infra.errors import AuthenticationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal


class CreateRuntimeApiKeyController(Controller):
    def __init__(self, use_case: CreateRuntimeApiKeyUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        principal = request.principal
        body = dict(request.body or {})
        body["project_id"] = request.path_params["project_id"]
        if isinstance(principal, AuthenticatedPrincipal):
            body["created_by_user_id"] = principal.user_id
        elif isinstance(principal, ControlPlanePrincipal):
            body["created_by_control_key_id"] = principal.api_key_id
        else:
            raise AuthenticationError("Authentication required")
        input_dto = CreateRuntimeApiKeyInput(**body)
        result = await self._use_case.execute(input_dto)
        response_data = CreatedApiKeyResponse(
            id=result.id,
            credential_id=result.credential_id,
            project_id=result.project_id,
            name=result.name,
            description=result.description,
            key=result.key,
            key_prefix=result.key_prefix,
            scopes=result.scopes,
            kind=result.kind,
            agent_id=result.agent_id,
            target_type=result.target_type.value,
            target_id=result.target_id,
            environment=result.environment.value,
            interfaces=result.interfaces,
            status=result.status.value,
            expires_at=result.expires_at,
            created_at=result.created_at,
            rotated_from_id=None,
        )
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={
                "success": True,
                "message": "created",
                "data": response_data.model_dump(),
            },
        )

