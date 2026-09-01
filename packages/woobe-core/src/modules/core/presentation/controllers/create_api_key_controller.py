from modules.core.application.dtos import CreateApiKeyInput
from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.presentation.schemas import CreatedApiKeyResponse
from shared.infra.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class CreateApiKeyController(Controller):
    def __init__(self, use_case: CreateApiKeyUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthenticationError("User authentication required")
        body = dict(request.body or {})
        body["project_id"] = request.path_params["project_id"]
        body["created_by_user_id"] = principal.user_id
        input_dto = CreateApiKeyInput(**body)
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
            status=result.status.value,
            expires_at=result.expires_at,
            created_at=result.created_at,
            rotated_from_id=None,
        )
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": response_data.model_dump(),
            },
        )
