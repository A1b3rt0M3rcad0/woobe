from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from shared.contracts.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class AgentChatSurfaceMessage:
    id: UUID
    role: str
    content: str
    data: dict[str, Any] | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class AgentChatSurfaceMessagePage:
    items: tuple[AgentChatSurfaceMessage, ...]
    next_cursor: str | None
    has_next: bool


class AgentChatSurfaceHistoryReader:
    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:
        self._transactions = transactions

    async def list_messages(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
        chat_surface_id: UUID,
        limit: int,
        cursor: UUID | None,
    ) -> AgentChatSurfaceMessagePage:
        safe_limit = min(100, max(1, limit))

        async def read_messages(repositories: AgentRuntimeRepositories, _outbox):
            await repositories.environment.assert_enabled(
                agent_id=agent_id,
                project_id=project_id,
                environment="production",
            )
            if not await repositories.sessions.is_chat_surface_bound(
                session_id=session_id,
                project_id=project_id,
                agent_id=agent_id,
                agent_release_id=agent_release_id,
                chat_surface_id=chat_surface_id,
            ):
                raise NotFoundError("ChatSurface Session not found")

            page = await repositories.messages.paginate_by_session(
                session_id,
                limit=safe_limit,
                cursor=str(cursor) if cursor is not None else None,
            )
            items = [
                AgentChatSurfaceMessage(
                    id=message.id,
                    role=str(message.role),
                    content=message.content,
                    data=message.data,
                    created_at=message.created_at,
                )
                for message in page.items
            ]
            items.reverse()
            return AgentChatSurfaceMessagePage(
                items=tuple(items),
                next_cursor=page.next_cursor,
                has_next=page.has_next,
            )

        return await self._transactions.read(read_messages)


def build_agent_chat_surface_history_reader() -> AgentChatSurfaceHistoryReader:
    return AgentChatSurfaceHistoryReader(
        AgentRuntimeTransactionRunner(
            build_agent_uow,
            build_agent_read_uow,
        )
    )


__all__ = [
    "AgentChatSurfaceHistoryReader",
    "AgentChatSurfaceMessage",
    "AgentChatSurfaceMessagePage",
    "build_agent_chat_surface_history_reader",
]
