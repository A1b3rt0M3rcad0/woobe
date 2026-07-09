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
from modules.agent.application.use_cases.runtime_use_cases import CreateAskJobUseCase
from modules.agent.domain.errors import AskJobNotFoundError
from modules.agent.domain.repositories import AskJobRepository
from shared.infra.errors import AuthenticationError, AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import ProjectApiPrincipal


InternalHandler = Callable[[Request], Awaitable[Response]]
EnvironmentPreflight = Callable[[UUID, str], Awaitable[None]]


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
    return {
        **payload.model_dump(),
        "project_id": principal.project_id,
        "agent_id": principal.agent_id,
        "execution_context": principal.environment,
    }


class PublicRunController(Controller):
    def __init__(
        self,
        internal_handler: InternalHandler,
        environment_preflight: EnvironmentPreflight,
    ) -> None:
        self._internal_handler = internal_handler
        self._environment_preflight = environment_preflight

    async def handle(self, request: Request) -> Response:
        principal = require_runtime_principal(request)
        await self._environment_preflight(principal.agent_id, principal.environment)
        payload = PublicRunRequest(**(request.body or {}))
        internal_request = request.model_copy(
            update={"body": build_internal_runtime_body(payload, principal)}
        )
        return await self._internal_handler(internal_request)


class PublicCreateJobController(Controller):
    def __init__(
        self,
        use_case: CreateAskJobUseCase,
        environment_preflight: EnvironmentPreflight,
    ) -> None:
        self._use_case = use_case
        self._environment_preflight = environment_preflight

    async def handle(self, request: Request) -> Response:
        principal = require_runtime_principal(request)
        await self._environment_preflight(principal.agent_id, principal.environment)
        payload = PublicCreateJobRequest(**(request.body or {}))
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
        if (
            job.project_id != principal.project_id
            or job.agent_id != principal.agent_id
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
