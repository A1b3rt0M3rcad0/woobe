from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)


def _uuid_or_none(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


class FrozenSnapshotStructuredOutputRuntime(TransactionBoundedStructuredOutputRuntime):
    """Apply a rerun Draft snapshot exactly instead of inheriting current Draft state."""

    def _apply_snapshot_override(self, agent, snapshot: dict):
        # Do not call the compatibility implementation from AskAgentUseCase here.
        # Rerun needs exact replacement semantics, including explicit nulls, and
        # must use the Agent SessionMode enum (stateful/stateless).
        if "system_prompt" in snapshot:
            agent.system_prompt = snapshot.get("system_prompt") or ""
        if "provider_model_id" in snapshot:
            agent.provider_model_id = _uuid_or_none(snapshot.get("provider_model_id"))
        if "provider_credential_id" in snapshot:
            agent.provider_credential_id = _uuid_or_none(
                snapshot.get("provider_credential_id")
            )
        if "provider" in snapshot and snapshot.get("provider") is not None:
            provider = snapshot.get("provider")
            agent.provider = Provider(provider) if isinstance(provider, str) else provider
        if "model" in snapshot:
            agent.model = snapshot.get("model") or ""
        if "fallback_provider_model_id" in snapshot:
            agent.fallback_provider_model_id = _uuid_or_none(
                snapshot.get("fallback_provider_model_id")
            )
        if "fallback_credential_id" in snapshot:
            agent.fallback_credential_id = _uuid_or_none(
                snapshot.get("fallback_credential_id")
            )
        if "fallback_provider" in snapshot:
            fallback_provider = snapshot.get("fallback_provider")
            agent.fallback_provider = (
                Provider(fallback_provider)
                if isinstance(fallback_provider, str) and fallback_provider
                else fallback_provider
            )
        if "fallback_model" in snapshot:
            agent.fallback_model = snapshot.get("fallback_model")
        if "temperature" in snapshot:
            agent.temperature = snapshot.get("temperature")
        if "max_output_tokens" in snapshot:
            agent.max_output_tokens = snapshot.get("max_output_tokens")
        if "session_mode" in snapshot and snapshot.get("session_mode") is not None:
            session_mode = snapshot.get("session_mode")
            agent.session_mode = (
                SessionMode(session_mode) if isinstance(session_mode, str) else session_mode
            )

        settings = deepcopy(agent.settings or {})
        if "response_format" in snapshot:
            response_format = deepcopy(snapshot.get("response_format"))
            if response_format is None:
                settings.pop("response_format", None)
            else:
                settings["response_format"] = response_format
        if "runtime_config" in snapshot:
            settings["runtime_config"] = deepcopy(snapshot.get("runtime_config") or {})
        if "knowledge_version_id" in snapshot:
            knowledge_version_id = snapshot.get("knowledge_version_id")
            if knowledge_version_id:
                settings["knowledge_version_id"] = str(knowledge_version_id)
            else:
                settings.pop("knowledge_version_id", None)
        agent.settings = settings
        return agent
