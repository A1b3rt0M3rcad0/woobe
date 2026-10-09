"""Owner projection for immutable constituent publication and exact hash proof."""
from modules.agent.domain.execution_definition import canonical_value, hash_agent_execution_snapshot
from modules.agent.infra.database.asac_publisher import frozen_release_entity
from modules.agent.infra.database.models import AgentReleaseModel
from shared.contracts.errors import ConflictError


class AgentFrozenSnapshotReader:
    def __init__(self, *, snapshot_builder):
        self.snapshot_builder = snapshot_builder

    async def read(self, session, *, project_id, resource_id, snapshot_id, expected_kind):
        row = await session.get(AgentReleaseModel, snapshot_id)
        if (row is None or row.project_id != project_id or row.agent_id != resource_id
            or row.snapshot_kind != expected_kind):
            raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID: exact constituent is unavailable")
        entity = frozen_release_entity(row)
        return {"project_id": str(project_id), "resource_id": str(resource_id),
            "snapshot_id": str(row.id), "snapshot_kind": row.snapshot_kind,
            "release_version": row.version, "release_status": row.status,
            "runtime_digest": "sha256:" + hash_agent_execution_snapshot(entity),
            "runtime_snapshot": canonical_value(self.snapshot_builder(entity))}
