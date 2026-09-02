import json
from datetime import UTC, datetime, timedelta

from modules.chat_surface.application.dtos.message_request import (
    BeginMessageRequestInput,
    BeginMessageRequestResult,
    LatestMessageRequestInput,
    MarkMessageRequestInput,
    MessageRequestState,
)
from modules.chat_surface.application.interfaces.message_request_repository import (
    ChatSurfaceMessageRequestRepository,
)
from shared.contracts.errors import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


class BeginChatSurfaceMessageUseCase:
    def __init__(
        self,
        repository: ChatSurfaceMessageRequestRepository,
        *,
        max_metadata_bytes: int,
    ) -> None:
        self._repository = repository
        self._max_metadata_bytes = max_metadata_bytes

    async def execute(
        self,
        input_dto: BeginMessageRequestInput,
    ) -> BeginMessageRequestResult:
        idempotency_key = input_dto.idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValidationError("A valid Idempotency-Key is required")
        if input_dto.metadata is not None:
            encoded = json.dumps(
                input_dto.metadata,
                separators=(",", ":"),
                default=str,
            ).encode()
            if len(encoded) > self._max_metadata_bytes:
                raise ValidationError("ChatSurface metadata is too large")

        now = datetime.now(UTC)
        surface = await self._repository.lock_surface_for_admission(
            surface_id=input_dto.surface_id,
            session_binding_id=input_dto.session_binding_id,
        )
        if surface is None:
            raise NotFoundError("ChatSurface Session not found")
        if surface.status != "active":
            raise ConflictError("ChatSurface is not active")

        await self._repository.expire_stale(
            surface_id=input_dto.surface_id,
            stale_before=now - timedelta(minutes=10),
            completed_at=now,
        )

        existing = await self._repository.find_idempotent(
            session_binding_id=input_dto.session_binding_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return BeginMessageRequestResult(request=existing, created=False)

        one_minute_ago = now - timedelta(minutes=1)
        if (
            await self._repository.count_surface_requests(
                surface_id=input_dto.surface_id,
                since=one_minute_ago,
            )
            >= surface.requests_per_minute
        ):
            raise RateLimitError(
                "ChatSurface request rate limit exceeded",
                retry_after=60,
            )
        if (
            await self._repository.count_session_requests(
                session_binding_id=input_dto.session_binding_id,
                since=one_minute_ago,
            )
            >= 30
        ):
            raise RateLimitError(
                "ChatSurface Session message rate limit exceeded",
                retry_after=60,
            )
        if (
            await self._repository.count_surface_active(input_dto.surface_id)
            >= surface.max_concurrent_runs
        ):
            raise RateLimitError(
                "ChatSurface concurrency limit exceeded",
                retry_after=1,
            )

        created = await self._repository.create(
            session_binding_id=input_dto.session_binding_id,
            idempotency_key=idempotency_key,
        )
        return BeginMessageRequestResult(request=created, created=True)


class LatestChatSurfaceMessageUseCase:
    def __init__(self, repository: ChatSurfaceMessageRequestRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: LatestMessageRequestInput,
    ) -> MessageRequestState | None:
        return await self._repository.latest_for_binding(input_dto.session_binding_id)


class MarkChatSurfaceMessageUseCase:
    def __init__(self, repository: ChatSurfaceMessageRequestRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None:
        return await self._repository.mark(input_dto)
