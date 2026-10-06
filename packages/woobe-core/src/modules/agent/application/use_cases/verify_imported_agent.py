from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.domain.enums import AgentStatus, CredentialStatus
from shared.contracts.errors import ConflictError


class VerifyImportedAgentUseCase:
    def __init__(self, agents, releases, credentials, knowledge_validator):
        self._agents, self._releases, self._credentials, self._knowledge = (
            agents,
            releases,
            credentials,
            knowledge_validator,
        )

    async def execute(self, definition):
        agent = await self._agents.get_by_id(definition.agent_id)
        draft = await self._releases.get_by_id(definition.draft_id)
        if (
            agent is None
            or draft is None
            or agent.project_id != definition.project_id
            or draft.project_id != definition.project_id
            or draft.agent_id != agent.id
            or agent.status != AgentStatus.active
            or getattr(draft, "snapshot_kind", None) != "draft"
        ):
            raise ConflictError(
                "Imported Agent has no active projection and complete Draft"
            )
        if build_agent_execution_snapshot(agent) != build_agent_execution_snapshot(
            draft
        ):
            raise ConflictError(
                "Imported Agent projection differs from its complete Draft"
            )
        for identifier in (draft.provider_credential_id, draft.fallback_credential_id):
            if identifier is None:
                continue
            credential = await self._credentials.get_by_id(identifier)
            if (
                credential is None
                or credential.project_id != definition.project_id
                or credential.status != CredentialStatus.active
            ):
                raise ConflictError("Imported Agent credential is unavailable")
        await self._knowledge.validate(draft)
        if definition.lifecycle != "draft":
            snapshot = await self._releases.get_by_id(definition.release_id)
            expected_kind = (
                "staging" if definition.lifecycle == "staging" else "release"
            )
            if (
                snapshot is None
                or snapshot.project_id != definition.project_id
                or snapshot.agent_id != agent.id
                or getattr(snapshot, "snapshot_kind", None) != expected_kind
                or build_agent_execution_snapshot(snapshot)
                != build_agent_execution_snapshot(draft)
            ):
                raise ConflictError(
                    "Imported Agent lifecycle snapshot differs from its Draft"
                )
            if definition.lifecycle == "production":
                production = await self._releases.get_active_production(agent.id)
                if production is None or production.id != snapshot.id:
                    raise ConflictError("Imported Agent Release is not active")
            await self._knowledge.validate(snapshot)
        return {
            "id": str(agent.id),
            "draft_id": str(draft.id),
            "configuration_ready": True,
            "execution_ready": True,
            "lifecycle_state": definition.lifecycle,
        }
