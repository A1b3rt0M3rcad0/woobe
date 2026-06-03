from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.observability.domain.entities import Trace, TraceEvent


class TraceRepository(ABC):

    @abstractmethod
    async def save(self, trace: Trace) -> Trace: ...

    @abstractmethod
    async def get_by_id(self, trace_id: UUID) -> Trace | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]: ...

    @abstractmethod
    async def delete(self, trace_id: UUID) -> None: ...


class TraceEventRepository(ABC):

    @abstractmethod
    async def save(self, event: TraceEvent) -> TraceEvent: ...

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> TraceEvent | None: ...

    @abstractmethod
    async def list_by_trace(
        self, trace_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[TraceEvent]: ...

    @abstractmethod
    async def delete(self, event_id: UUID) -> None: ...
