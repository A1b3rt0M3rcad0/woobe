from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.history_repository import (
    SQLAlchemyNetworkHistoryRepository,
)
from modules.network.infra.database.session_repository import (
    SQLAlchemyNetworkRuntimeEnvironmentRepository,
    SQLAlchemyNetworkSessionRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.contracts.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class NetworkChatSurfaceMessage:
    id: UUID
    role: str
    content: str
    data: dict[str, Any] | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class NetworkChatSurfaceMessagePage:
    items: tuple[NetworkChatSurfaceMessage, ...]
    next_cursor: str | None
    has_next: bool


class NetworkChatSurfaceHistoryReader:
    async def list_messages(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
        chat_surface_id: UUID,
        limit: int,
        cursor: UUID | None,
    ) -> NetworkChatSurfaceMessagePage:
        safe_limit = min(100, max(1, limit))
        async with NetworkUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            environment_repository = SQLAlchemyNetworkRuntimeEnvironmentRepository(uow)
            await environment_repository.require_enabled(
                network_id=network_id,
                project_id=project_id,
                environment="production",
            )
            session_repository = SQLAlchemyNetworkSessionRepository(uow)
            if not await session_repository.is_chat_surface_bound(
                session_id=network_session_id,
                project_id=project_id,
                network_id=network_id,
                network_version_id=network_version_id,
                chat_surface_id=chat_surface_id,
            ):
                raise NotFoundError("ChatSurface Session not found")

            history_repository = SQLAlchemyNetworkHistoryRepository(uow)
            items, next_cursor, has_next = (
                await history_repository.list_chat_surface_messages(
                    network_session_id=network_session_id,
                    project_id=project_id,
                    limit=safe_limit,
                    cursor=cursor,
                )
            )
            return NetworkChatSurfaceMessagePage(
                items=tuple(
                    NetworkChatSurfaceMessage(
                        id=message.id,
                        role=message.role,
                        content=message.content,
                        data=message.data,
                        created_at=message.created_at,
                    )
                    for message in items
                ),
                next_cursor=next_cursor,
                has_next=has_next,
            )


def build_network_chat_surface_history_reader() -> NetworkChatSurfaceHistoryReader:
    return NetworkChatSurfaceHistoryReader()


__all__ = [
    "NetworkChatSurfaceHistoryReader",
    "NetworkChatSurfaceMessage",
    "NetworkChatSurfaceMessagePage",
    "build_network_chat_surface_history_reader",
]
