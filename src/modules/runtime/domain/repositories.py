from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.runtime.domain.entities import Message, Session


class SessionRepository(ABC):

    @abstractmethod
    async def create(self, session: Session) -> Session: ...

    @abstractmethod
    async def get_by_id(self, session_id: UUID) -> Session: ...

    @abstractmethod
    async def get_by_external_id(
        self, project_id: UUID, agent_id: UUID, external_session_id: str
    ) -> Session: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Session]: ...

    @abstractmethod
    async def update(self, session: Session) -> Session: ...

    @abstractmethod
    async def delete(self, session_id: UUID) -> None: ...


class MessageRepository(ABC):

    @abstractmethod
    async def create(self, message: Message) -> Message: ...

    @abstractmethod
    async def get_by_id(self, message_id: UUID) -> Message: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[Message]: ...

    @abstractmethod
    async def count_by_session(self, session_id: UUID) -> int: ...

    @abstractmethod
    async def delete_by_session(self, session_id: UUID) -> None: ...

