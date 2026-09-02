"""Explicit public persistence/release surface used by Network composition.

Network and Agent promotions share one database transaction. These symbols are
exposed through the Agent entrypoint so Network never imports Agent internals
by package path. The boundary remains intentionally narrow and exists only for
cross-context release orchestration.
"""

from modules.agent.application.use_cases.network_snapshot_lifecycle import (
    NetworkAgentSnapshotLifecycle,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.mappers import agent_release_model_to_entity
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository

__all__ = [
    "AgentModel",
    "AgentRelease",
    "AgentReleaseModel",
    "NetworkAgentSnapshotLifecycle",
    "SQLAlchemyAgentReleaseRepository",
    "agent_release_model_to_entity",
    "calculate_next_release_version",
    "classify_release_change",
    "release_snapshot_hash",
    "release_snapshots_equal",
]
