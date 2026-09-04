from modules.agent.application.interfaces.use_case import UseCase
from collections.abc import Awaitable, Callable
from uuid import UUID

from modules.agent.application.dtos.public_runtime_dtos import (
    PublicCreateJobRequest,
    PublicRunRequest,
)
from modules.agent.application.dtos.runtime_dtos import CreateAskJobInput
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller
from shared.security.principal import ProjectApiPrincipal


InternalHandler = Callable[[OperationRequest], Awaitable[OperationResult]]
RequestPreparer = Callable[
    [PublicRunRequest, UUID, UUID, str],
    Awaitable[PublicRunRequest],
]


def require_runtime_principal(request: OperationRequest) -> ProjectApiPrincipal:
    principal = request.principal
    if not isinstance(principal, ProjectApiPrincipal):
        raise AuthenticationError("Runtime Key authentication required")
    if principal.kind != "runtime":
        raise AuthorizationError("A Runtime Key is required for this endpoint")
    if principal.agent_id is None or principal.environment is None:
        raise AuthorizationError("Runtime Key binding is incomplete")
    return principal


def build_internal_runtime_body(
    payload: PublicRunRequest,
    principal: ProjectApiPrincipal,
) -> dict:
    body = payload.model_dump()
    metadata = dict(payload.metadata or {})
    metadata.setdefault("source", "public_runtime")
    return {
        **body,
        "metadata": metadata,
        "project_id": principal.project_id,
        "agent_id": principal.agent_id,
        "execution_context": principal.environment,
    }


class PublicRunController(Controller):
    def __init__(
        self,
        internal_handler: InternalHandler,
        request_preparer: RequestPreparer,
    ) -> None:
        self._internal_handler = internal_handler
        self._request_preparer = request_preparer

    async def handle(self, request: OperationRequest) -> OperationResult:
        principal = require_runtime_principal(request)
        payload = PublicRunRequest(**(request.body or {}))
        payload = await self._request_preparer(
            payload,
            principal.project_id,
            principal.agent_id,
            principal.environment,
        )
        internal_request = request.model_copy(
            update={"body": build_internal_runtime_body(payload, principal)}
        )
        return await self._internal_handler(internal_request)


class PublicCreateJobController(Controller):
    def __init__(
        self,
        use_case: UseCase,
        request_preparer: RequestPreparer,
    ) -> None:
        self._use_case = use_case
        self._request_preparer = request_preparer

    async def handle(self, request: OperationRequest) -> OperationResult:
        principal = require_runtime_principal(request)
        payload = PublicCreateJobRequest(**(request.body or {}))
        payload = await self._request_preparer(
            payload,
            principal.project_id,
            principal.agent_id,
            principal.environment,
        )
        input_dto = CreateAskJobInput(
            **build_internal_runtime_body(payload, principal)
        )
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={
                "success": True,
                "message": "Ask job created",
                "data": result.model_dump(),
            },
        )


class PublicGetJobController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        principal = require_runtime_principal(request)
        job_id = UUID(request.path_params["job_id"])
        result = await self._use_case.execute(
            job_id,
            project_id=principal.project_id,
            agent_id=principal.agent_id,
            environment=principal.environment,
        )
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": result.model_dump(),
            },
        )

