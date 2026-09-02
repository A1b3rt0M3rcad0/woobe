from modules.identity.application.dtos import RegisterInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.presentation.authentication_response import (
    AuthenticationCookiePolicy,
    authentication_response,
)
from shared.contracts.errors import ValidationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class InstanceStatusController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        del request
        data = await self._use_case.execute()
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class BootstrapInstanceController(Controller):
    def __init__(
        self,
        use_case: UseCase,
        cookie_policy: AuthenticationCookiePolicy,
    ) -> None:
        self._use_case = use_case
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        data = RegisterInput(**(request.body or {}))
        result = await self._use_case.execute(
            email=data.email,
            password=data.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client_ip,
        )
        return authentication_response(
            request,
            result,
            self._cookie_policy,
            status_code=201,
        )


class BootstrapExistingOwnerController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        owner_email = body.get("owner_email")
        if not isinstance(owner_email, str) or not owner_email.strip():
            raise ValidationError("owner_email is required")
        owner_id = await self._use_case.execute(owner_email=owner_email)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "initialized",
                "data": {"owner_user_id": str(owner_id)},
            },
        )
