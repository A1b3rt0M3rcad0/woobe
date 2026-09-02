from modules.core.application.dtos import CreateProjectInput
from modules.core.application.interfaces.use_case import UseCase
from modules.core.presentation.schemas import ProjectResponse
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


class CreateProjectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthenticationError("User authentication required")
        body = dict(request.body or {})
        body["actor_user_id"] = principal.user_id
        input_dto = CreateProjectInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": ProjectResponse(**result.model_dump()).model_dump(),
            },
        )
