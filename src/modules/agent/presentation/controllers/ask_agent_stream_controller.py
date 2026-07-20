import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.application.dtos import AskInput
from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from shared.runtime_environment import assert_runtime_environment_enabled


def _sse_type(chunk: str) -> str | None:
    for line in chunk.splitlines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
            return event_type or None
    for line in chunk.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line.removeprefix("data:").strip())
        except (json.JSONDecodeError, TypeError):
            return None
        event_type = payload.get("type") if isinstance(payload, dict) else None
        return event_type if isinstance(event_type, str) else None
    return None


async def commit_safe_stream(
    service: Any,
    input_dto: Any,
    fastapi_request: FastAPIRequest | None = None,
) -> AsyncGenerator[str, None]:
    pending_terminal: str | None = None
    source = (
        service.stream(input_dto, fastapi_request.is_disconnected)
        if fastapi_request is not None
        else service.stream(input_dto)
    )

    async for chunk in source:
        event_type = _sse_type(chunk)
        if event_type in {"done", "error", "cancelled"}:
            pending_terminal = chunk
            continue
        yield chunk

    if pending_terminal is not None:
        yield pending_terminal


async def handle_ask_stream(
    fastapi_request: FastAPIRequest,
    service: AskAgentStreamService,
) -> StreamingResponse:
    received_at = datetime.now(timezone.utc).isoformat()
    body: dict = await fastapi_request.json()
    metadata = body.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["server_received_at"] = received_at
    body["metadata"] = metadata
    input_dto = AskInput(**body)

    async with fastapi_request.app.state.session_factory() as session, session.begin():
        await assert_runtime_environment_enabled(
            session,
            target_type="agent",
            target_id=input_dto.agent_id,
            project_id=input_dto.project_id,
            environment=input_dto.execution_context,
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
