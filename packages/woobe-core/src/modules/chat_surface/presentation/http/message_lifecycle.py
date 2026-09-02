from uuid import UUID

from modules.chat_surface.application.dtos.message_request import MessageRequestState
from modules.chat_surface.composition.composers.message_lifecycle_composers import (
    begin_chat_surface_message_runtime_composer,
    latest_chat_surface_message_composer,
    mark_chat_surface_message_runtime_composer,
)
from shared.presentation.http.request import Request as InternalRequest


async def begin_message_request(
    *,
    surface_id: UUID,
    session_binding_id: UUID,
    idempotency_key: str,
    metadata: dict | None = None,
) -> tuple[MessageRequestState, bool]:
    handler = begin_chat_surface_message_runtime_composer()
    result = await handler(
        surface_id=surface_id,
        session_binding_id=session_binding_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )
    return result.request, result.created


async def latest_message_request(
    session_binding_id: UUID,
) -> MessageRequestState | None:
    response = await latest_chat_surface_message_composer()(
        InternalRequest(
            path_params={"session_binding_id": str(session_binding_id)},
        )
    )
    data = response.body["data"]
    return MessageRequestState.model_validate(data) if data is not None else None


async def mark_message_request(
    request_id: UUID,
    *,
    status: str,
    target_run_id: UUID | None = None,
    error_code: str | None = None,
) -> MessageRequestState | None:
    handler = mark_chat_surface_message_runtime_composer()
    return await handler(
        request_id,
        status=status,
        target_run_id=target_run_id,
        error_code=error_code,
    )


__all__ = [
    "begin_message_request",
    "latest_message_request",
    "mark_message_request",
]
