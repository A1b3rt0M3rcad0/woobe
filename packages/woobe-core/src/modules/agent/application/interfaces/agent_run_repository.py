from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.agent.domain.run import AgentRun


class AgentRunRepository(ABC):
    @abstractmethod
    async def create(self, run: AgentRun) -> AgentRun: ...

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> AgentRun | None: ...

    @abstractmethod
    async def get_by_trace_id(self, trace_id: UUID) -> AgentRun | None: ...

    @abstractmethod
    async def get_output_message_content(self, message_id: UUID) -> str | None: ...

    @abstractmethod
    async def list_model_invocations(self, run_id: UUID) -> list[dict]: ...

    @abstractmethod
    async def list_direct(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None = None,
        environment: str | None = None,
        limit: int = 100,
    ) -> list[AgentRun]: ...

    @abstractmethod
    async def get_active_direct_by_session(
        self,
        session_id: UUID,
    ) -> AgentRun | None: ...

    @abstractmethod
    async def resolve_direct_runtime_run(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> AgentRun | None: ...

    @abstractmethod
    async def save(self, run: AgentRun) -> AgentRun: ...
