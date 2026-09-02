"""Explicit public Agent integration surface used by Network composition.

The boundary is intentionally narrow: Network may query Agent availability and
orchestrate immutable Agent snapshots through the Agent entrypoint without
importing Agent internals by package path.
"""

from uuid import UUID

from modules.agent.application.use_cases.network_snapshot_lifecycle import (
    NetworkAgentSnapshotLifecycle,
)
from modules.agent.composition.factories.agent_uow_factory import build_agent_read_uow
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.mappers import agent_release_model_to_entity
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentReleaseRepository,
    SQLAlchemyAgentRepository,
)


class NetworkAgentAvailabilityReader:
    """Read-only Agent availability boundary for Network Draft validation."""

    async def unavailable_active_agent_ids(
        self,
        *,
        project_id: UUID,
        agent_ids: set[UUID],
    ) -> set[UUID]:
        if not agent_ids:
            return set()
        uow = build_agent_read_uow()
        repository = SQLAlchemyAgentRepository(uow)
        async with uow:
            agents = await repository.list_by_project(project_id)
        available = {
            agent.id
            for agent in agents
            if agent.id in agent_ids
            and str(getattr(agent.status, "value", agent.status)) == "active"
        }
        return agent_ids - available


__all__ = [
    "AgentModel",
    "AgentRelease",
    "AgentReleaseModel",
    "NetworkAgentAvailabilityReader",
    "NetworkAgentSnapshotLifecycle",
    "SQLAlchemyAgentReleaseRepository",
    "agent_release_model_to_entity",
    "calculate_next_release_version",
    "classify_release_change",
    "release_snapshot_hash",
    "release_snapshots_equal",
]
