import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from modules.agent.application.dtos import AskInput


def _sse_type(chunk: str) -> str | None:
    if not chunk.startswith("data:"):
        return None
    try:
        payload = json.loads(chunk.removeprefix("data:").strip())
    except (json.JSONDecodeError, TypeError):
        return None
    event_type = payload.get("type")
    return event_type if isinstance(event_type, str) else None


async def _commit_safe_stream(
    service: AskAgentStreamService,
    input_dto: AskInput,
    fastapi_request: FastAPIRequest,
) -> AsyncGenerator[str, None]:
    pending_terminal: str | None = None

    async for chunk in service.generate(
        input_dto,
        fastapi_request.is_disconnected,
    ):
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

    return StreamingResponse(
        _commit_safe_stream(service, input_dto, fastapi_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
