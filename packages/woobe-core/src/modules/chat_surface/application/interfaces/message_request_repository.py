from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.chat_surface.application.dtos.message_request import (
    MarkMessageRequestInput,
    MessageAdmissionSurfaceState,
    MessageRequestRuntimeContext,
    MessageRequestState,
)


class ChatSurfaceMessageRequestRepository(ABC):
    @abstractmethod
    async def get(self, request_id: UUID) -> MessageRequestState | None: ...

    @abstractmethod
    async def get_runtime_context(
        self,
        request_id: UUID,
    ) -> MessageRequestRuntimeContext | None: ...

    @abstractmethod
    async def latest_for_binding(
        self,
        session_binding_id: UUID,
    ) -> MessageRequestState | None: ...

    @abstractmethod
    async def lock_surface_for_admission(
        self,
        *,
        surface_id: UUID,
        session_binding_id: UUID,
    ) -> MessageAdmissionSurfaceState | None: ...

    @abstractmethod
    async def expire_stale(
        self,
        *,
        session_binding_id: UUID,
        stale_before: datetime,
        completed_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def find_idempotent(
        self,
        *,
        session_binding_id: UUID,
        idempotency_key: str,
    ) -> MessageRequestState | None: ...

    @abstractmethod
    async def count_surface_requests(
        self,
        *,
        surface_id: UUID,
        since: datetime,
    ) -> int: ...

    @abstractmethod
    async def count_session_requests(
        self,
        *,
        session_binding_id: UUID,
        since: datetime,
    ) -> int: ...

    @abstractmethod
    async def count_surface_active(self, surface_id: UUID) -> int: ...

    @abstractmethod
    async def create(
        self,
        *,
        session_binding_id: UUID,
        idempotency_key: str,
    ) -> MessageRequestState: ...

    @abstractmethod
    async def mark(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None: ...
