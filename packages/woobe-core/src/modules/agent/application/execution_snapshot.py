from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from modules.agent.application.skill_bindings import frozen_enabled_skills, skill_bindings
from modules.agent.domain.enums import AgentStatus, Provider, ReleaseStatus, SessionMode
from modules.agent.domain.errors import AgentNotFoundError, RuntimeEnvironmentNotReadyError
from modules.agent.domain.execution_definition import canonicalize_agent_execution_definition
from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
from shared.contracts.errors import ValidationError


_EXECUTION_ENVIRONMENTS = {"draft", "staging", "production"}
_RELEASE_SOURCE_BY_STATUS = {
    ReleaseStatus.draft.value: "draft",
    ReleaseStatus.staging.value: "staging",
    ReleaseStatus.released.value: "release",
    ReleaseStatus.production.value: "release",
}


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _uuid(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Agent execution snapshot contains an invalid UUID reference") from exc


def _uuid_text(value: Any) -> str | None:
    parsed = _uuid(value)
    return str(parsed) if parsed is not None else None


def _runtime_config(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("Agent execution snapshot runtime_config must be an object")
    return deepcopy(value)


def _release_sort_key(release: Any) -> float:
    value = getattr(release, "updated_at", None) or getattr(release, "created_at", None)
    return value.timestamp() if value is not None else 0.0


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


def validate_agent_draft_projection(agent_settings: Any, draft_runtime_config: Any) -> None:
    """Reject a split-brain saved Draft instead of silently dropping Skills."""
    settings = agent_settings if isinstance(agent_settings, dict) else {}
    agent_runtime = settings.get("runtime_config")
    if _skill_binding_signature(agent_runtime) != _skill_binding_signature(
        draft_runtime_config
    ):
        raise ValidationError(
            "Agent Draft Skill bindings are out of sync with the saved Draft snapshot. "
            "Save the Agent Draft again before executing it."
        )


def _validate_frozen_skills(runtime_config: dict[str, Any], project_id: UUID) -> None:
    if "skills" in runtime_config:
        frozen_enabled_skills(runtime_config, project_id)


def build_agent_execution_snapshot(source: Any) -> dict[str, Any]:
    """Materialize one canonical runtime snapshot from Agent or AgentRelease state."""
    project_id = _uuid(getattr(source, "project_id", None))
    if project_id is None:
        raise ValidationError("Agent execution snapshot has no valid Project")

    runtime_config = _runtime_config(
        getattr(source, "runtime_config", None)
        if hasattr(source, "runtime_config")
        else (getattr(source, "settings", None) or {}).get("runtime_config")
    )
    _validate_frozen_skills(runtime_config, project_id)

    settings = dict(getattr(source, "settings", None) or {})
    provider = _value(getattr(source, "provider", None))
    model = getattr(source, "model", None)
    session_mode = _value(getattr(source, "session_mode", None))
    if not provider or not model:
        raise ValidationError("Agent execution snapshot has no executable model configuration")
    if session_mode not in {SessionMode.stateful.value, SessionMode.stateless.value}:
        raise ValidationError("Agent execution snapshot has no valid Session Mode")

    response_format = (
        deepcopy(getattr(source, "response_format", None))
        if hasattr(source, "response_format")
        else deepcopy(settings.get("response_format"))
    )
    external_context_contract = (
        deepcopy(getattr(source, "external_context_contract", None))
        if hasattr(source, "external_context_contract")
        else deepcopy(settings.get("external_context_contract"))
    )
    base_url = (
        getattr(source, "base_url", None)
        if hasattr(source, "base_url")
        else settings.get("base_url")
    )
    knowledge_version_id = (
        getattr(source, "knowledge_version_id", None)
        if hasattr(source, "knowledge_version_id")
        else settings.get("knowledge_version_id")
    )

    complete = canonicalize_agent_execution_definition(source)
    for field in complete:
        if not hasattr(source, field) and field in settings:
            complete[field] = deepcopy(settings[field])
    if complete["agent_status"] is None and hasattr(source, "settings"):
        complete["agent_status"] = _value(getattr(source, "status", None))
    for prefix in ("", "fallback_"):
        spec_field = f"{prefix}model_spec_snapshot"
        raw = settings.get(f"{prefix}model_spec")
        if complete[spec_field] is None and isinstance(raw, dict):
            spec = ModelSpec.from_dict(raw)
            complete[spec_field] = spec.as_dict()
            complete[f"{prefix}model_spec_hash"] = model_spec_hash(spec)
    return {
        **complete,
        "name": getattr(source, "name", None),
        "description": getattr(source, "description", None),
        "behavior_spec": deepcopy(getattr(source, "behavior_spec", None)),
        "system_prompt": getattr(source, "system_prompt", None) or "",
        "response_format": response_format,
        "external_context_contract": external_context_contract,
        "provider": str(provider),
        "model": str(model),
        "provider_credential_id": _uuid_text(
            getattr(source, "provider_credential_id", None)
        ),
        "provider_model_id": _uuid_text(getattr(source, "provider_model_id", None)),
        "fallback_provider": _value(getattr(source, "fallback_provider", None)),
        "fallback_model": getattr(source, "fallback_model", None),
        "fallback_credential_id": _uuid_text(
            getattr(source, "fallback_credential_id", None)
        ),
        "fallback_provider_model_id": _uuid_text(
            getattr(source, "fallback_provider_model_id", None)
        ),
        "base_url": base_url,
        "temperature": getattr(source, "temperature", None),
        "max_output_tokens": getattr(source, "max_output_tokens", None),
        "session_mode": str(session_mode),
        "knowledge_version_id": _uuid_text(knowledge_version_id),
        "runtime_config": runtime_config,
    }


def apply_agent_execution_snapshot(agent: Any, snapshot: dict[str, Any]) -> Any:
    """Apply a complete canonical snapshot with replacement semantics."""
    project_id = _uuid(getattr(agent, "project_id", None))
    if project_id is None:
        raise ValidationError("Agent execution target has no valid Project")
    runtime_config = _runtime_config(snapshot.get("runtime_config"))
    _validate_frozen_skills(runtime_config, project_id)

    provider = snapshot.get("provider")
    model = snapshot.get("model")
    session_mode = snapshot.get("session_mode")
    if not provider or not model:
        raise ValidationError("Agent execution snapshot has no executable model configuration")
    if session_mode not in {SessionMode.stateful.value, SessionMode.stateless.value}:
        raise ValidationError("Agent execution snapshot has no valid Session Mode")

    if snapshot.get("name") is not None:
        agent.name = snapshot["name"]
    if snapshot.get("description") is not None:
        agent.description = snapshot["description"]
    agent.behavior_spec = deepcopy(snapshot.get("behavior_spec"))
    agent.system_prompt = str(snapshot.get("system_prompt") or "")
    agent.provider = Provider(str(provider))
    agent.model = str(model)
    agent.provider_credential_id = _uuid(snapshot.get("provider_credential_id"))
    agent.provider_model_id = _uuid(snapshot.get("provider_model_id"))
    fallback_provider = snapshot.get("fallback_provider")
    agent.fallback_provider = Provider(str(fallback_provider)) if fallback_provider else None
    agent.fallback_model = snapshot.get("fallback_model")
    agent.fallback_credential_id = _uuid(snapshot.get("fallback_credential_id"))
    agent.fallback_provider_model_id = _uuid(snapshot.get("fallback_provider_model_id"))
    agent.temperature = snapshot.get("temperature")
    agent.max_output_tokens = snapshot.get("max_output_tokens")
    agent.session_mode = SessionMode(str(session_mode))

    settings = dict(getattr(agent, "settings", None) or {})
    for key in (
        "response_format",
        "external_context_contract",
        "base_url",
        "knowledge_version_id",
        "prompt_version_id",
        "contract_version_id",
        "model_config_version_id",
        "output_schema",
        "model_spec_snapshot",
        "model_spec_hash",
        "fallback_model_spec_snapshot",
        "fallback_model_spec_hash",
        "collection_ids",
        "risk_score",
    ):
        value = snapshot.get(key)
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = deepcopy(value)
    settings["runtime_config"] = runtime_config
    for prefix in ("", "fallback_"):
        model_spec = snapshot.get(f"{prefix}model_spec_snapshot")
        if model_spec is None:
            settings.pop(f"{prefix}model_spec", None)
        else:
            settings[f"{prefix}model_spec"] = deepcopy(model_spec)
    agent.settings = settings
    return agent


@dataclass(frozen=True, slots=True)
class ResolvedAgentExecutionSnapshot:
    environment: str
    source: str
    snapshot: dict[str, Any]
    release: Any | None = None

    @property
    def release_id(self) -> UUID | None:
        return _uuid(getattr(self.release, "id", None)) if self.release is not None else None

    @property
    def release_version(self) -> str | None:
        value = getattr(self.release, "version", None) if self.release is not None else None
        return str(value) if value not in {None, ""} else None

    @property
    def release_status(self) -> str | None:
        value = _value(getattr(self.release, "status", None)) if self.release is not None else None
        return str(value) if value not in {None, ""} else None

    @property
    def snapshot_kind(self) -> str | None:
        value = getattr(self.release, "snapshot_kind", None) if self.release is not None else None
        return str(value) if value not in {None, ""} else None


class AgentExecutionSnapshotResolver:
    """Single Agent execution resolution path for Draft, Staging and Production.

    Environment controls which persisted snapshot may be selected. Snapshot
    materialization and validation are identical after selection.
    """

    def __init__(self, agent_repo: Any | None = None, release_repo: Any | None = None) -> None:
        self._agent_repo = agent_repo
        self._release_repo = release_repo

    @staticmethod
    def normalize_environment(value: str | None) -> str:
        raw = str(value or "draft").strip().lower()
        if raw in {"playground", "development"}:
            raw = "draft"
        if raw == "release":
            raw = "production"
        if raw not in _EXECUTION_ENVIRONMENTS:
            raise ValueError("Unsupported execution context")
        return raw

    @staticmethod
    def _source_from_release(release: Any) -> str:
        status = str(_value(getattr(release, "status", None)) or "")
        source = _RELEASE_SOURCE_BY_STATUS.get(status)
        if source is None:
            raise ValidationError("Agent Release is not executable")
        return source

    @staticmethod
    def _validate_environment_policy(environment: str, release: Any) -> str:
        source = AgentExecutionSnapshotResolver._source_from_release(release)
        if environment == "production" and source != "release":
            raise ValidationError("Production requires an immutable Agent Release")
        if environment == "staging" and source == "draft":
            raise ValidationError("Staging cannot execute an Agent Draft")
        return source

    def resolve_loaded(
        self,
        *,
        project_id: UUID,
        agent: Any,
        environment: str,
        release: Any | None,
        allow_legacy_draft: bool = False,
        validate_draft_projection: bool = False,
    ) -> ResolvedAgentExecutionSnapshot:
        environment = self.normalize_environment(environment)
        if _uuid(getattr(agent, "project_id", None)) != project_id:
            raise AgentNotFoundError(getattr(agent, "id", None))
        status = _value(getattr(agent, "status", None))
        if status not in {None, AgentStatus.active.value}:
            raise ValidationError("Agent is not active")

        if release is None:
            if environment != "draft" or not allow_legacy_draft:
                raise RuntimeEnvironmentNotReadyError(environment, getattr(agent, "id", None))
            return ResolvedAgentExecutionSnapshot(
                environment="draft",
                source="draft",
                snapshot=build_agent_execution_snapshot(agent),
                release=None,
            )

        if (
            _uuid(getattr(release, "project_id", None)) != project_id
            or _uuid(getattr(release, "agent_id", None)) != _uuid(getattr(agent, "id", None))
        ):
            raise ValidationError("Pinned Agent release was not found")

        source = self._validate_environment_policy(environment, release)
        if source == "draft" and validate_draft_projection:
            validate_agent_draft_projection(
                getattr(agent, "settings", None),
                getattr(release, "runtime_config", None),
            )
        return ResolvedAgentExecutionSnapshot(
            environment=environment,
            source=source,
            snapshot=build_agent_execution_snapshot(release),
            release=release,
        )

    async def resolve(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
        release_id: UUID | None = None,
        allow_legacy_draft: bool = False,
        validate_draft_projection: bool = False,
    ) -> ResolvedAgentExecutionSnapshot:
        if self._agent_repo is None:
            raise RuntimeError("Agent execution snapshot resolver has no Agent repository")
        agent = await self._agent_repo.get_by_id(agent_id)
        if agent is None or _uuid(getattr(agent, "project_id", None)) != project_id:
            raise AgentNotFoundError(agent_id)

        environment = self.normalize_environment(environment)
        release = None
        if release_id is not None:
            if self._release_repo is None:
                raise ValidationError(
                    f"{environment.title()} runtime requires release repository"
                )
            release = await self._release_repo.get_by_id(release_id)
            if release is None:
                raise ValidationError("Pinned Agent release was not found")
        elif self._release_repo is not None:
            if environment == "production":
                release = await self._release_repo.get_active_production(agent_id)
            else:
                status = (
                    ReleaseStatus.draft
                    if environment == "draft"
                    else ReleaseStatus.staging
                )
                releases = await self._release_repo.list_by_status(agent_id, status)
                release = max(releases, key=_release_sort_key) if releases else None

        if release is None and environment != "draft":
            if self._release_repo is None:
                raise ValidationError(
                    f"{environment.title()} runtime requires release repository"
                )
            raise RuntimeEnvironmentNotReadyError(environment, agent_id)

        return self.resolve_loaded(
            project_id=project_id,
            agent=agent,
            environment=environment,
            release=release,
            allow_legacy_draft=allow_legacy_draft,
            validate_draft_projection=validate_draft_projection,
        )
