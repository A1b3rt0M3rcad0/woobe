from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.domain.enums import (
    AgentStatus,
    CredentialStatus,
    ProviderModelStatus,
    ToolStatus,
)
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from modules.agent.application.model_spec_compatibility import LegacyModelSpecResolver
from modules.agent.application.tool_release_snapshots import (
    tool_to_release_snapshot,
    tool_from_release_snapshot,
)
from modules.agent.application.tool_types import is_mcp_tool_type
from modules.agent.application.interfaces.mcp_readiness import build_mcp_readiness
from uuid import UUID
from shared.contracts.errors import ConflictError


class VerifyImportedAgentUseCase:
    def __init__(
        self, agents, releases, credentials, knowledge_validator, *, models, tools
    ):
        self._models, self._tools = models, tools
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
        for prefix, credential_field in (
            ("", "provider_credential_id"),
            ("fallback_", "fallback_credential_id"),
        ):
            model_id = getattr(draft, prefix + "provider_model_id", None)
            specification = getattr(draft, prefix + "model_spec_snapshot", None)
            expected_hash = getattr(draft, prefix + "model_spec_hash", None)
            if prefix and model_id is None:
                continue
            model = await self._models.get_by_id(model_id) if model_id else None
            effective_spec = None
            if model is not None:
                effective_spec = (
                    ModelSpec.from_dict(model.spec)
                    if model.spec is not None
                    else LegacyModelSpecResolver().resolve(
                        model, provider=str(getattr(draft, prefix + "provider"))
                    )
                )
            if (
                model is None
                or model.project_id != definition.project_id
                or model.status != ProviderModelStatus.active
                or model.provider_credential_id != getattr(draft, credential_field)
                or effective_spec.as_dict() != specification
                or model.spec_hash is not None
                and model.spec_hash != expected_hash
                or model_spec_hash(effective_spec) != expected_hash
            ):
                raise ConflictError(
                    "Imported Model differs from its complete executable snapshot"
                )
        tool_config = (draft.runtime_config or {}).get("tools") or {}
        snapshots = tool_config.get("snapshots") or []
        if {str(snapshot["id"]) for snapshot in snapshots} != set(
            map(str, tool_config.get("tool_ids") or [])
        ):
            raise ConflictError("Imported Agent Tool closure is incomplete")
        for snapshot in snapshots:
            frozen = tool_from_release_snapshot(snapshot)
            tool = await self._tools.get_by_id(UUID(str(snapshot["id"])))
            if (
                tool is None
                or tool.project_id != definition.project_id
                or tool.status != ToolStatus.ACTIVE
                or tool_to_release_snapshot(tool) != snapshot
            ):
                raise ConflictError("Imported Tool changed after Draft capture")
            if (
                is_mcp_tool_type(frozen.type)
                and not build_mcp_readiness(tool.config, tool.status)["mcp_ready"]
            ):
                raise ConflictError("Imported MCP Tool is not ready")
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
