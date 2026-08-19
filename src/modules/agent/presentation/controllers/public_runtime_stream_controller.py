from modules.agent.application.interfaces.use_case import UseCase
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.presentation.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from shared.contracts.errors import AuthenticationError, AuthorizationError
from shared.runtime_environment import assert_runtime_environment_enabled
from shared.security.principal import ProjectApiPrincipal


RequestPreparer = Callable[
    [PublicRunRequest, UUID, UUID, str],
    Awaitable[PublicRunRequest],
]


async def handle_public_run_stream(
    fastapi_request: FastAPIRequest,
    service: UseCase,
    request_preparer: RequestPreparer,
) -> StreamingResponse:
    principal = getattr(fastapi_request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal):
        raise AuthenticationError("Runtime Key authentication required")
    if principal.kind != "runtime":
        raise AuthorizationError("A Runtime Key is required for this endpoint")
    if principal.agent_id is None or principal.environment is None:
        raise AuthorizationError("Runtime Key binding is incomplete")

    async with fastapi_request.app.state.session_factory() as session, session.begin():
        await assert_runtime_environment_enabled(
            session,
            target_type="agent",
            target_id=principal.agent_id,
            project_id=principal.project_id,
            environment=principal.environment,
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
