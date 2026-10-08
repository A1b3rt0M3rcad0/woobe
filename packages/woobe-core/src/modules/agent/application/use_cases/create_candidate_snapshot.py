"""Create a detached immutable native snapshot, never a singleton environment."""

from uuid import UUID

from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeCreateReleaseUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import AgentStatus, ReleaseStatus
from modules.agent.domain.errors import AgentNotFoundError
from shared.contracts.errors import ConflictError


class CreateCandidateSnapshot:
    def __init__(self, *, agents, releases, preparation: KnowledgeSafeCreateReleaseUseCase):
        self.agents, self.releases, self.preparation = agents, releases, preparation

    async def execute(self, definition, *, snapshot_id: UUID):
        agent = await self.agents.get_by_id(definition.agent_id)
        if agent is None or agent.project_id != definition.project_id or agent.status == AgentStatus.archived:
            raise AgentNotFoundError(definition.agent_id)
        # Input is the complete compiled sealed object. In particular, do not
        # fill absent fields from today's mutable Agent or singleton Draft.
        prepared = await self.preparation.prepare_snapshot(definition)
        snapshot = AgentRelease(id=snapshot_id, project_id=definition.project_id,
            agent_id=definition.agent_id, version=snapshot_id.hex,
            status=ReleaseStatus.archived)
        snapshot.snapshot_kind = "candidate"
        AutoCreateReleaseUseCase(self.releases)._copy_input_to_release(prepared, snapshot)
        executable = build_agent_execution_snapshot(snapshot)
        existing = await self.releases.get_by_id(snapshot_id)
        if existing is not None:
            if (existing.project_id != snapshot.project_id or existing.agent_id != snapshot.agent_id
                or getattr(existing, "snapshot_kind", None) != "candidate"
                or build_agent_execution_snapshot(existing) != executable):
                raise ConflictError("ASAC_CANDIDATE_SNAPSHOT_CONFLICT: immutable identity has another snapshot")
            return existing
        return await self.releases.save(snapshot)
