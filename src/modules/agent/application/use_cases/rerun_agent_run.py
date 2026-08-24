from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.interfaces.agent_run_rerun import (
    AgentRunExecutor,
    AgentRunRerunReader,
)
from modules.agent.domain.run import AgentRunStatus
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError


def _draft_snapshot_override(execution_snapshot: dict) -> dict:
    raw_agent = execution_snapshot.get("agent")
    if not isinstance(raw_agent, dict):
        raise ValidationError("Agent Run has no reusable draft snapshot")

    settings = deepcopy(raw_agent.get("settings") or {})
    runtime_config = deepcopy(settings.get("runtime_config") or {})
    raw_tools = execution_snapshot.get("tools")
    if isinstance(raw_tools, list):
        tools_config = deepcopy(runtime_config.get("tools") or {})
        snapshots = [deepcopy(item) for item in raw_tools if isinstance(item, dict)]
        tools_config["snapshots"] = snapshots
        tools_config["tool_ids"] = [
            str(item["id"])
            for item in snapshots
            if item.get("id") is not None
        ]
        runtime_config["tools"] = tools_config

    raw_knowledge = execution_snapshot.get("knowledge")
    frozen_knowledge_version_id = settings.get("knowledge_version_id")
    if isinstance(raw_knowledge, dict) and raw_knowledge.get("knowledge_version_id"):
        frozen_knowledge_version_id = raw_knowledge["knowledge_version_id"]

    return {
        "system_prompt": raw_agent.get("system_prompt"),
        "response_format": settings.get("response_format"),
        "provider_model_id": raw_agent.get("provider_model_id"),
        "provider_credential_id": raw_agent.get("provider_credential_id"),
        "provider": raw_agent.get("provider"),
        "model": raw_agent.get("model"),
        "fallback_provider_model_id": raw_agent.get("fallback_provider_model_id"),
        "fallback_credential_id": raw_agent.get("fallback_credential_id"),
        "fallback_provider": raw_agent.get("fallback_provider"),
        "fallback_model": raw_agent.get("fallback_model"),
        "temperature": raw_agent.get("temperature"),
        "max_output_tokens": raw_agent.get("max_output_tokens"),
        "session_mode": raw_agent.get("session_mode"),
        "knowledge_version_id": frozen_knowledge_version_id,
        "runtime_config": runtime_config,
    }


class RerunAgentRunUseCase:
    """Create a new logical Run from an existing terminal Agent Run."""

    def __init__(
        self,
        reader: AgentRunRerunReader,
        executor: AgentRunExecutor,
    ) -> None:
        self._reader = reader
        self._executor = executor

    async def execute(self, *, run_id: UUID, project_id: UUID) -> AskOutput:
        source = await self._reader.get_by_id(run_id)
        if source is None or source.project_id != project_id:
            raise NotFoundError("Agent Run not found")
        if source.status == AgentRunStatus.RUNNING:
            raise ConflictError("A running Agent Run cannot be rerun")

        execution_context = source.environment
        loaded_release_id = source.agent_release_id
        snapshot_override = None
        if source.environment == "draft":
            execution_context = "playground"
            loaded_release_id = None
            snapshot_override = _draft_snapshot_override(source.execution_snapshot)
        elif source.environment not in {"staging", "production"}:
            raise ValidationError("Agent Run has an unsupported environment")

        metadata = {
            "source": "rerun",
            "rerun_of_run_id": str(source.id),
        }
        if source.input_message_id is not None:
            metadata["reuse_input_message_id"] = str(source.input_message_id)

        return await self._executor.execute(
            AskInput(
                project_id=source.project_id,
                agent_id=source.agent_id,
                message=source.input_message,
                session_id=source.session_id,
                metadata=metadata,
                execution_context=execution_context,
                loaded_release_id=loaded_release_id,
                snapshot_override=snapshot_override,
            )
        )
