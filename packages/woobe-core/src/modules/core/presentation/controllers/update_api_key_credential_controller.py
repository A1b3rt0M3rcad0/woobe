from modules.core.application.dtos import UpdateApiKeyCredentialInput
from modules.core.application.use_cases import UpdateApiKeyCredentialUseCase
from modules.core.presentation.schemas import ApiKeyCredentialResponse
from shared.infra.errors import AuthenticationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class UpdateApiKeyCredentialController(Controller):
    def __init__(self, use_case: UpdateApiKeyCredentialUseCase) -> None:
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
                "updated_by_user_id": principal.user_id,
            }
        )
        result = await self._use_case.execute(UpdateApiKeyCredentialInput(**body))
        response_data = ApiKeyCredentialResponse(
            id=result.id,
            credential_id=result.credential_id,
            project_id=result.project_id,
            name=result.name,
            description=result.description,
            kind=result.kind.value,
            agent_id=result.agent_id,
            target_type=result.target_type.value if result.target_type else None,
            target_id=result.target_id,
            environment=result.environment.value if result.environment else None,
            updated_at=result.updated_at,
        )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "updated",
                "data": response_data.model_dump(),
            },
        )

