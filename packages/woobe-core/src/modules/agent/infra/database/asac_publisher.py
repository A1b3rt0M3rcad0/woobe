"""Native Agent publication copies exact executable fields without selection."""
from copy import deepcopy
from uuid import uuid4
from sqlalchemy import select
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.models import AgentReleaseModel
from modules.agent.infra.database.mappers import agent_release_model_to_entity, agent_release_entity_to_model
from shared.contracts.errors import ConflictError


def frozen_release_entity(model):
    # The base legacy mapper omits canonical Provider Model references. Match
    # the native candidate/runtime repository rather than hashing a projection.
    entity = agent_release_model_to_entity(model)
    entity.provider_model_id = getattr(model, "provider_model_id", None)
    entity.fallback_provider_model_id = getattr(model, "fallback_provider_model_id", None)
    return entity


class AgentASaCPublisher:
    async def publish(self, *, session, project_id, resource_id, candidate, principal, reason):
        source = await session.get(AgentReleaseModel, candidate.root_snapshot_id)
        if source is None or source.project_id != project_id or source.agent_id != resource_id or source.snapshot_kind != "candidate":
            raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID")
        frozen = frozen_release_entity(source)
        digest = "sha256:" + hash_agent_execution_snapshot(frozen)
        if digest != candidate.runtime_digest:
            raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
        releases = (await session.scalars(select(AgentReleaseModel).where(
            AgentReleaseModel.project_id == project_id, AgentReleaseModel.agent_id == resource_id,
            AgentReleaseModel.snapshot_kind == "release").order_by(AgentReleaseModel.created_at.desc(), AgentReleaseModel.id.desc()))).all()
        for released in releases:
            if "sha256:" + hash_agent_execution_snapshot(frozen_release_entity(released)) == digest:
                return {"release_id":released.id, "release_version":released.version, "reused":True, "runtime_digest":digest}
        current = next((frozen_release_entity(row) for row in releases if row.status == "production"), None)
        clone = deepcopy(frozen)
        clone.id = uuid4()
        clone.version = calculate_next_release_version([row.version for row in releases], classify_release_change(current, frozen))
        clone.status, clone.snapshot_kind = ReleaseStatus.released, "release"
        clone.release_notes, clone.created_by = reason, getattr(principal, "user_id", None)
        clone.promoted_by = clone.promoted_at = clone.created_at = clone.updated_at = None
        native = agent_release_entity_to_model(clone)
        native.provider_model_id = getattr(frozen,"provider_model_id",None)
        native.fallback_provider_model_id = getattr(frozen,"fallback_provider_model_id",None)
        session.add(native)
        await session.flush()
        if "sha256:" + hash_agent_execution_snapshot(frozen_release_entity(native)) != digest:
            raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
        return {"release_id":native.id, "release_version":native.version, "reused":False, "runtime_digest":digest}
