from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import PublicRunRequest
from modules.agent.entrypoint import AskInput
from modules.agent.entrypoint import RuntimeEnvironmentGuard
from modules.agent.entrypoint import UseCase
from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.security.principal import ProjectApiPrincipal


RequestPreparer = Callable[
    [PublicRunRequest, UUID, UUID, str],
    Awaitable[PublicRunRequest],
]


async def handle_public_run_stream(
    fastapi_request: FastAPIRequest,
    service: UseCase,
    request_preparer: RequestPreparer,
    environment_guard: RuntimeEnvironmentGuard,
) -> StreamingResponse:
    principal = getattr(fastapi_request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal):
        raise AuthenticationError("Runtime Key authentication required")
    if principal.kind != "runtime":
        raise AuthorizationError("A Runtime Key is required for this endpoint")
    if principal.agent_id is None or principal.environment is None:
        raise AuthorizationError("Runtime Key binding is incomplete")

    await environment_guard(
        principal.agent_id,
        principal.project_id,
        principal.environment,
    )

    payload = PublicRunRequest(**(await fastapi_request.json()))
    payload = await request_preparer(
        payload,
        principal.project_id,
        principal.agent_id,
        principal.environment,
    )
    metadata = dict(payload.metadata or {})
    metadata["server_received_at"] = datetime.now(timezone.utc).isoformat()
    input_dto = AskInput(
        **payload.model_dump(exclude={"metadata"}),
        metadata=metadata,
        project_id=principal.project_id,
        agent_id=principal.agent_id,
        execution_context=principal.environment,
    )

    return StreamingResponse(
        commit_safe_stream(service, input_dto, fastapi_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class PublicRuntimeStreamController:
    def __init__(
        self,
        service: UseCase,
        request_preparer: RequestPreparer,
        environment_guard: RuntimeEnvironmentGuard,
    ) -> None:
        self._service = service
        self._request_preparer = request_preparer
        self._environment_guard = environment_guard

    async def handle(self, request: FastAPIRequest) -> StreamingResponse:
        return await handle_public_run_stream(
            request,
            self._service,
            self._request_preparer,
            self._environment_guard,
        )

