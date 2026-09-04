from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

DisconnectCheck = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class ChatRuntimeTarget:
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID


@dataclass(frozen=True, slots=True)
class ChatRunIdentity:
    run_id: UUID
    status: str


@dataclass(frozen=True, slots=True)
class ChatMessageRequestSnapshot:
    id: UUID
    status: str
    created_at: datetime
    target_run_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ChatRuntimeRequest:
    project_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    surface_id: UUID
    message_request_id: UUID
    message: str
    metadata: dict
    session_source: str
    created: bool
    existing_run_id: UUID | None = None

    @property
    def target(self) -> ChatRuntimeTarget:
        return ChatRuntimeTarget(
            project_id=self.project_id,
            target_type=self.target_type,
            target_id=self.target_id,
            target_release_id=self.target_release_id,
            session_id=self.session_id,
        )


@dataclass(frozen=True, slots=True)
class ChatRuntimeChunk:
    sse: str
    run_id: UUID | None = None
    terminal_status: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedChatRuntime:
    stream: AsyncIterator[ChatRuntimeChunk]
    run_id: UUID | None = None
    headers: dict[str, str] | None = None


class ChatRuntimeGateway(Protocol):
    async def prepare(
        self,
        request: ChatRuntimeRequest,
        disconnect_check: DisconnectCheck,
    ) -> PreparedChatRuntime: ...

    async def resolve_run(
        self,
        target: ChatRuntimeTarget,
        *,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> ChatRunIdentity | None: ...

    async def observe(
        self,
        target: ChatRuntimeTarget,
        run_id: UUID,
        disconnect_check: DisconnectCheck,
    ) -> PreparedChatRuntime: ...

    async def cancel(
        self,
        target: ChatRuntimeTarget,
        run_id: UUID,
    ) -> ChatRunIdentity: ...
