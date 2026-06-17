import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.application.use_cases.ask_agent_stream_service import AskAgentStreamService
from modules.agent.application.dtos import AskInput


void_datetime = datetime
void_timezone = timezone


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
) -> AsyncGenerator[str, None]:
    pending_done: str | None = None

    async for chunk in service.generate(input_dto):
        event_type = _sse_type(chunk)
        if event_type == "done":
            pending_done = chunk
            continue
        if event_type == "error":
            pending_done = None
        yield chunk

    if pending_done is not None:
        yield pending_done


async def handle_ask_stream(
    fastapi_request: FastAPIRequest,
    service: AskAgentStreamService,
) -> StreamingResponse:
    body: dict = await fastapi_request.json()
    input_dto = AskInput(**body)

    return StreamingResponse(
        _commit_safe_stream(service, input_dto),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
