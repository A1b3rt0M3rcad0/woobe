from __future__ import annotations

from copy import deepcopy
from typing import Any

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.execution_snapshot import (
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver


class CanonicalExecutionSnapshotRuntimeResolver(ReleaseRuntimeResolver):
    """Resolve persisted Agent execution state through one canonical snapshot service."""

    async def _load_agent(self, uow: Any, input_dto: AskInput):
        agent = await self._load_base_agent(uow, input_dto)
        release_repo = getattr(uow, "releases", None)
        execution_context = (input_dto.execution_context or "playground").lower()
        environment = AgentExecutionSnapshotResolver.normalize_environment(execution_context)
        runtime_context = current_execution.get()
        if runtime_context is not None:
            runtime_context.execution_context = execution_context

        session_release_id = await self._session_runtime_binding(uow, input_dto)
        effective_release_id = session_release_id or input_dto.loaded_release_id
        resolver = AgentExecutionSnapshotResolver(uow.agents, release_repo)

        if effective_release_id is not None:
            resolved = await resolver.resolve(
                project_id=input_dto.project_id,
                agent_id=input_dto.agent_id,
                environment=environment,
                release_id=effective_release_id,
            )
            if resolved.release is not None:
                input_dto.loaded_release_id = resolved.release_id
                self._bind_release_context(resolved.release)
            agent = apply_agent_execution_snapshot(agent, resolved.snapshot)
            return await self._resolve_provider_model_refs(uow, agent)

        if environment == "draft" and input_dto.snapshot_override:
            snapshot_override = deepcopy(input_dto.snapshot_override)
            merged_runtime_config = await self._merge_playground_runtime_config(
                release_repo,
                agent.id,
                snapshot_override.get("runtime_config"),
            )
            if "runtime_config" in snapshot_override:
                snapshot_override["runtime_config"] = merged_runtime_config
            agent = self._apply_snapshot_override(agent, snapshot_override)
            agent = self._apply_runtime_config_snapshot(agent, merged_runtime_config)
            self._apply_snapshot_provider_model_ids(agent, snapshot_override)
            return await self._resolve_provider_model_refs(uow, agent)

        resolved = await resolver.resolve(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            environment=environment,
            allow_legacy_draft=environment == "draft",
            validate_draft_projection=environment == "draft",
        )
        if resolved.release is not None:
            self._bind_release_context(resolved.release)
            if environment != "draft":
                input_dto.loaded_release_id = resolved.release_id
        agent = apply_agent_execution_snapshot(agent, resolved.snapshot)
        return await self._resolve_provider_model_refs(uow, agent)


__all__ = ["CanonicalExecutionSnapshotRuntimeResolver"]
