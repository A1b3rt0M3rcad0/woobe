from modules.agent.application.interfaces.use_case import UseCase
from collections.abc import Awaitable, Callable
from uuid import UUID

from modules.agent.application.dtos.public_runtime_dtos import (
    PublicCreateJobRequest,
    PublicRunRequest,
)
from modules.agent.application.dtos.runtime_dtos import (
    CreateAskJobInput,
    GetAskJobOutput,
)
from modules.agent.domain.errors import AskJobNotFoundError
from modules.agent.application.interfaces.repositories import AskJobRepository
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import ProjectApiPrincipal


InternalHandler = Callable[[Request], Awaitable[Response]]
RequestPreparer = Callable[
    [PublicRunRequest, UUID, UUID, str],
    Awaitable[PublicRunRequest],
]


def require_runtime_principal(request: Request) -> ProjectApiPrincipal:
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

    async def handle(self, request: Request) -> Response:
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

    async def handle(self, request: Request) -> Response:
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
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "Ask job created",
                "data": result.model_dump(),
            },
        )


class PublicGetJobController(Controller):
    def __init__(self, repo: AskJobRepository) -> None:
        self._repo = repo

    async def handle(self, request: Request) -> Response:
        principal = require_runtime_principal(request)
        job_id = UUID(request.path_params["job_id"])
        job = await self._repo.get_by_id(job_id)
        job_environment = (job.params or {}).get("execution_context")
        if (
            job.project_id != principal.project_id
            or job.agent_id != principal.agent_id
            or job_environment != principal.environment
        ):
            raise AskJobNotFoundError(job_id)

        result = GetAskJobOutput(
            job_id=job.id,
            status=job.status,
            result=job.result,
            error=job.error,
            trace_id=job.trace_id,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": result.model_dump(),
            },
        )
