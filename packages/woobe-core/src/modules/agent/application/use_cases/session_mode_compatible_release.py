from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.domain.errors import AgentNotFoundError
from shared.contracts.errors import ConflictError, ValidationError


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _uuid_or_none(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Agent Draft contains an invalid UUID reference") from exc


def _draft_defaults_from_agent(agent: Any) -> dict[str, Any]:
    settings = dict(agent.settings or {})
    response_format = deepcopy(settings.get("response_format"))
    output_schema = (
        deepcopy(response_format.get("schema"))
        if isinstance(response_format, dict)
        else None
    )
    return {
        "name": agent.name,
        "description": agent.description,
        "behavior_spec": deepcopy(getattr(agent, "behavior_spec", None)),
        "system_prompt": agent.system_prompt,
        "response_format": response_format,
        "output_schema": output_schema,
        "external_context_contract": deepcopy(
            settings.get("external_context_contract")
        ),
        "provider": _enum_value(agent.provider),
        "model": agent.model,
        "provider_credential_id": agent.provider_credential_id,
        "provider_model_id": getattr(agent, "provider_model_id", None),
        "fallback_provider": _enum_value(agent.fallback_provider),
        "fallback_model": agent.fallback_model,
        "fallback_credential_id": agent.fallback_credential_id,
        "fallback_provider_model_id": getattr(
            agent, "fallback_provider_model_id", None
        ),
        "base_url": settings.get("base_url"),
        "temperature": agent.temperature,
        "max_output_tokens": agent.max_output_tokens,
        "session_mode": _enum_value(agent.session_mode),
        "agent_status": _enum_value(agent.status),
        "knowledge_version_id": _uuid_or_none(settings.get("knowledge_version_id")),
        "runtime_config": deepcopy(settings.get("runtime_config")),
    }


def _complete_draft_input(input_dto: Any, agent: Any) -> Any:
    fields_set = set(getattr(input_dto, "model_fields_set", set()))
    if (
        getattr(agent, "behavior_spec", None) is not None
        and "system_prompt" in fields_set
        and "behavior_spec" not in fields_set
    ):
        raise ConflictError("Update behavior_spec for an Agent with structured Behavior")
    if (
        "behavior_spec" in fields_set
        and input_dto.behavior_spec is None
        and "system_prompt" not in fields_set
    ):
        raise ConflictError("Clearing behavior_spec requires explicit legacy system_prompt")
    defaults = _draft_defaults_from_agent(agent)
    updates = {
        field_name: value
        for field_name, value in defaults.items()
        if field_name not in fields_set
    }
    return input_dto.model_copy(update=updates) if updates else input_dto


def _sync_agent_projection(agent: Any, draft: Any) -> None:
    if draft.name is not None:
        agent.name = draft.name
    agent.description = draft.description if draft.description is not None else ""
    agent.behavior_spec = deepcopy(getattr(draft, "behavior_spec", None))
    agent.system_prompt = draft.system_prompt if draft.system_prompt is not None else ""

    if draft.provider is None or draft.model is None:
        raise ValidationError("Agent Draft must contain an executable model configuration")
    agent.provider = Provider(str(draft.provider))
    agent.model = str(draft.model)
    agent.provider_credential_id = draft.provider_credential_id
    agent.provider_model_id = draft.provider_model_id
    agent.fallback_provider = (
        Provider(str(draft.fallback_provider)) if draft.fallback_provider else None
    )
    agent.fallback_model = draft.fallback_model
    agent.fallback_credential_id = draft.fallback_credential_id
    agent.fallback_provider_model_id = draft.fallback_provider_model_id
    agent.temperature = draft.temperature
    agent.max_output_tokens = draft.max_output_tokens

    if draft.session_mode not in {"stateful", "stateless"}:
        raise ValidationError("Agent snapshot session_mode must be stateful or stateless")
    agent.session_mode = SessionMode(str(draft.session_mode))

    settings = dict(agent.settings or {})
    if draft.response_format is None:
        settings.pop("response_format", None)
    else:
        settings["response_format"] = deepcopy(draft.response_format)
    external_context_contract = getattr(draft, "external_context_contract", None)
    if external_context_contract is None:
        settings.pop("external_context_contract", None)
    else:
        settings["external_context_contract"] = deepcopy(external_context_contract)
    if draft.base_url is None:
        settings.pop("base_url", None)
    else:
        settings["base_url"] = draft.base_url
    if draft.knowledge_version_id is None:
        settings.pop("knowledge_version_id", None)
    else:
        settings["knowledge_version_id"] = str(draft.knowledge_version_id)
    settings["runtime_config"] = deepcopy(draft.runtime_config or {})
    agent.settings = settings


class SessionModeCompatibleCreateReleaseUseCase:
    """Save one complete Agent Draft and keep its Agent projection atomic.

    The Draft Release is the executable authority. The Agent row remains the
    control-plane projection used by list/editor surfaces and is synchronized in
    the same Unit of Work, preventing Network Draft runs from observing a
    different Skill/runtime configuration than the saved Draft.
    """

    def __init__(self, delegate: Any, agent_repo: Any) -> None:
        self._delegate = delegate
        self._agent_repo = agent_repo

    async def execute(self, input_dto: Any, change_kind: str = "change") -> Any:
        agent = await self._agent_repo.get_by_id(input_dto.agent_id)
        if agent is None or agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)

        input_dto = _complete_draft_input(input_dto, agent)
        session_mode = getattr(input_dto, "session_mode", None)
        if session_mode not in {"stateful", "stateless"}:
            raise ValidationError("Agent snapshot session_mode must be stateful or stateless")

        draft = await self._delegate.execute(input_dto, change_kind=change_kind)
        _sync_agent_projection(agent, draft)
        await self._agent_repo.update(agent)
        return draft
