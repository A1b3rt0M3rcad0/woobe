from typing import Any, Protocol
from uuid import UUID


class AgentSnapshot(Protocol):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    name: str
    status: Any
    snapshot_kind: str
    session_mode: Any


class AgentPromotionGateway(Protocol):
    async def is_active_agent(self, *, project_id: UUID, agent_id: UUID) -> bool: ...

    async def latest_draft(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentSnapshot | None: ...

    async def snapshot_by_id(
        self,
        *,
        release_id: UUID | None,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentSnapshot | None: ...

    async def equivalent_snapshot(
        self,
        *,
        source: AgentSnapshot,
        target_kind: str,
        active_only: bool,
        lock: bool,
    ) -> AgentSnapshot | None: ...

    async def promote_draft_to_staging(
        self,
        source: AgentSnapshot,
        *,
        user_id: UUID | None,
    ) -> AgentSnapshot: ...

    async def publish_staging_for_network(
        self,
        source: AgentSnapshot,
        *,
        user_id: UUID | None,
    ) -> AgentSnapshot: ...

    def snapshot_hash(self, snapshot: AgentSnapshot) -> str: ...

    def snapshots_equal(self, left: AgentSnapshot, right: AgentSnapshot) -> bool: ...
