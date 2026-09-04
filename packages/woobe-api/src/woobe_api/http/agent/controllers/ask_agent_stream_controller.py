import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import AskInput
from modules.agent.entrypoint import RuntimeEnvironmentGuard
from modules.agent.entrypoint import UseCase


_PUBLIC_TOKEN_PHASES = {
    "response_generation",
    "capability_response_generation",
    "final_response_generation",
}


class DisconnectAwareRequest(Protocol):
    async def is_disconnected(self) -> bool: ...


def _sse_payload(chunk: str) -> dict[str, Any] | None:
    for line in chunk.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line.removeprefix("data:").strip())
        except (json.JSONDecodeError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _sse_type(chunk: str) -> str | None:
    for line in chunk.splitlines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
            return event_type or None
    payload = _sse_payload(chunk)
    event_type = payload.get("type") if payload else None
    return event_type if isinstance(event_type, str) else None


def _is_public_token_phase(phase: Any) -> bool:
    return (
        phase in _PUBLIC_TOKEN_PHASES
        or (isinstance(phase, str) and phase.startswith("tool_followup_"))
    )


def _is_public_stream_chunk(chunk: str) -> bool:
    if _sse_type(chunk) != "token":
        return True
    payload = _sse_payload(chunk)
    if payload is None:
        return False
    return (
        payload.get("visibility", "assistant") == "assistant"
        and payload.get("channel", "final") == "final"
        and _is_public_token_phase(payload.get("phase"))
    )


async def commit_safe_stream(
    service: Any,
    input_dto: Any,
    fastapi_request: DisconnectAwareRequest | None = None,
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
        if _is_public_stream_chunk(chunk):
            yield chunk

    if pending_terminal is not None:
        yield pending_terminal


async def handle_ask_stream(
    fastapi_request: FastAPIRequest,
    service: UseCase,
    environment_guard: RuntimeEnvironmentGuard,
) -> StreamingResponse:
    received_at = datetime.now(timezone.utc).isoformat()
    body: dict = await fastapi_request.json()
    metadata = body.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["server_received_at"] = received_at
    body["metadata"] = metadata
    input_dto = AskInput(**body)

    await environment_guard(
        input_dto.agent_id,
        input_dto.project_id,
        input_dto.execution_context,
    )

    return StreamingResponse(
        commit_safe_stream(service, input_dto, fastapi_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AskAgentStreamController:
    def __init__(
        self,
        service: UseCase,
        environment_guard: RuntimeEnvironmentGuard,
    ) -> None:
        self._service = service
        self._environment_guard = environment_guard

    async def handle(self, request: FastAPIRequest) -> StreamingResponse:
        return await handle_ask_stream(
            request,
            self._service,
            self._environment_guard,
        )

