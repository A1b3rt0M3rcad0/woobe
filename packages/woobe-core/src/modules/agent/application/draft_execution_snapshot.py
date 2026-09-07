from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.application.skill_bindings import (
    frozen_enabled_skills,
    skill_bindings,
)
from shared.contracts.errors import ValidationError


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _uuid_text(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _runtime_config(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("Agent Draft runtime_config must be an object")
    return deepcopy(value)


def _skill_binding_signature(runtime_config: Any) -> tuple[tuple[str, str, bool], ...]:
    config = skill_bindings(runtime_config)
    return tuple(
        sorted(
            (
                str(binding.skill_id),
                str(binding.skill_version_id),
                bool(binding.enabled),
            )
            for binding in config.bindings
        )
    )


def validate_agent_draft_skill_projection(
    agent_settings: Any,
    draft_runtime_config: Any,
) -> None:
    """Reject split-brain Drafts instead of silently dropping or inventing Skills."""
    settings = agent_settings if isinstance(agent_settings, dict) else {}
    agent_runtime = settings.get("runtime_config")
    if _skill_binding_signature(agent_runtime) != _skill_binding_signature(
        draft_runtime_config
    ):
        raise ValidationError(
            "Agent Draft Skill bindings are out of sync with the saved Draft snapshot. "
            "Save the Agent Draft again before running it in a Network."
        )


def _validate_frozen_skills(runtime_config: dict[str, Any], project_id: UUID) -> None:
    if "skills" not in runtime_config:
        return
    # The runtime uses the same invariant. Validate it when the Network accepts the
    # Draft so a bad binding fails explicitly instead of executing without a Skill.
    frozen_enabled_skills(runtime_config, project_id)


def build_draft_release_execution_snapshot(release: Any) -> dict[str, Any]:
    """Build the executable Draft snapshot from the saved Draft Release only."""
    project_id = getattr(release, "project_id", None)
    if not isinstance(project_id, UUID):
        try:
            project_id = UUID(str(project_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Agent Draft snapshot has no valid Project") from exc

    runtime_config = _runtime_config(getattr(release, "runtime_config", None))
    _validate_frozen_skills(runtime_config, project_id)

    provider = _enum_value(getattr(release, "provider", None))
    model = getattr(release, "model", None)
    session_mode = _enum_value(getattr(release, "session_mode", None))
    if not provider or not model:
        raise ValidationError(
            "Agent Draft snapshot has no executable model configuration. Save the Agent Draft again."
        )
    if session_mode not in {"stateful", "stateless"}:
        raise ValidationError(
            "Agent Draft snapshot has no valid Session Mode. Save the Agent Draft again."
        )

    return {
        "system_prompt": getattr(release, "system_prompt", None) or "",
        "response_format": deepcopy(getattr(release, "response_format", None)),
        "provider": str(provider),
        "model": str(model),
        "provider_credential_id": _uuid_text(
            getattr(release, "provider_credential_id", None)
        ),
        "provider_model_id": _uuid_text(getattr(release, "provider_model_id", None)),
        "fallback_provider": _enum_value(getattr(release, "fallback_provider", None)),
        "fallback_model": getattr(release, "fallback_model", None),
        "fallback_credential_id": _uuid_text(
            getattr(release, "fallback_credential_id", None)
        ),
        "fallback_provider_model_id": _uuid_text(
            getattr(release, "fallback_provider_model_id", None)
        ),
        "base_url": getattr(release, "base_url", None),
        "temperature": getattr(release, "temperature", None),
        "max_output_tokens": getattr(release, "max_output_tokens", None),
        "session_mode": str(session_mode),
        "knowledge_version_id": _uuid_text(
            getattr(release, "knowledge_version_id", None)
        ),
        "runtime_config": runtime_config,
    }


def build_legacy_agent_execution_snapshot(agent: Any) -> dict[str, Any]:
    """Compatibility path for Agents created before a saved Draft Release existed."""
    settings = dict(getattr(agent, "settings", None) or {})
    runtime_config = _runtime_config(settings.get("runtime_config"))
    project_id = getattr(agent, "project_id", None)
    if isinstance(project_id, UUID):
        _validate_frozen_skills(runtime_config, project_id)

    provider = _enum_value(getattr(agent, "provider", None))
    model = getattr(agent, "model", None)
    session_mode = _enum_value(getattr(agent, "session_mode", None))
    if not provider or not model:
        raise ValidationError("Agent Draft has no executable model configuration")
    if session_mode not in {"stateful", "stateless"}:
        raise ValidationError("Agent Draft has no valid Session Mode")

    return {
        "system_prompt": getattr(agent, "system_prompt", None) or "",
        "response_format": deepcopy(settings.get("response_format")),
        "provider": str(provider),
        "model": str(model),
        "provider_credential_id": _uuid_text(
            getattr(agent, "provider_credential_id", None)
        ),
        "provider_model_id": _uuid_text(getattr(agent, "provider_model_id", None)),
        "fallback_provider": _enum_value(getattr(agent, "fallback_provider", None)),
        "fallback_model": getattr(agent, "fallback_model", None),
        "fallback_credential_id": _uuid_text(
            getattr(agent, "fallback_credential_id", None)
        ),
        "fallback_provider_model_id": _uuid_text(
            getattr(agent, "fallback_provider_model_id", None)
        ),
        "base_url": settings.get("base_url"),
        "temperature": getattr(agent, "temperature", None),
        "max_output_tokens": getattr(agent, "max_output_tokens", None),
        "session_mode": str(session_mode),
        "knowledge_version_id": _uuid_text(settings.get("knowledge_version_id")),
        "runtime_config": runtime_config,
    }
