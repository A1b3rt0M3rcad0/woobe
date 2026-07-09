from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from modules.agent.presentation.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from shared.infra.errors import AuthenticationError, AuthorizationError
from shared.security.principal import ProjectApiPrincipal


EnvironmentPreflight = Callable[[UUID, str], Awaitable[None]]


async def handle_public_run_stream(
    fastapi_request: FastAPIRequest,
    service: AskAgentStreamService,
    environment_preflight: EnvironmentPreflight,
) -> StreamingResponse:
    principal = getattr(fastapi_request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal):
        raise AuthenticationError("Runtime Key authentication required")
    if principal.kind != "runtime":
        raise AuthorizationError("A Runtime Key is required for this endpoint")
    if principal.agent_id is None or principal.environment is None:
        raise AuthorizationError("Runtime Key binding is incomplete")

    await environment_preflight(principal.agent_id, principal.environment)
    payload = PublicRunRequest(**(await fastapi_request.json()))
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
