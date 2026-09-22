from __future__ import annotations

from typing import Any

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.agent.infra.execution.canonical_execution_snapshot_runtime_resolver import (
    CanonicalExecutionSnapshotRuntimeResolver,
)
from shared.contracts.errors import ConflictError, ValidationError
from shared.runtime_environment import normalize_runtime_environment

_LEGACY_RUNTIME_KEYS = {"runtime_environment", "loaded_release_id", "release_version"}


def _clean_session_data(value: Any) -> dict[str, Any]:
    data = dict(value) if isinstance(value, dict) else {}
    return {key: item for key, item in data.items() if key not in _LEGACY_RUNTIME_KEYS}


def _session_environment(session: Any) -> str:
    explicit = getattr(session, "runtime_environment", None)
    if explicit in {"draft", "staging", "production"}:
        return explicit
    data = getattr(session, "data", None)
    legacy = data.get("runtime_environment") if isinstance(data, dict) else None
    if legacy in {"draft", "staging", "production"}:
        return legacy
    return "draft"


class SessionContinuityReleaseRuntimeResolver(CanonicalExecutionSnapshotRuntimeResolver):
    """Standalone Sessions follow their environment; each Run freezes its Release.

    `opened_release_id` is provenance only. Network invocations keep the explicit
    immutable Agent Release binding supplied by the Network version.
    """

    async def _session_runtime_binding(self, uow: Any, input_dto: AskInput):
        if input_dto.session_id is None or self._is_network_runtime(input_dto):
            return None

        session_repo = getattr(uow, "sessions", None)
        if session_repo is None:
            return None
        session = await session_repo.get_by_id(input_dto.session_id)
        if session.project_id != input_dto.project_id or session.agent_id != input_dto.agent_id:
            raise ValidationError("Agent Session does not belong to this Agent runtime")

        requested_environment = normalize_runtime_environment(input_dto.execution_context)
        session_environment = _session_environment(session)
        if session_environment != requested_environment:
            raise ConflictError(
                f"Agent Session belongs to {session_environment}, not {requested_environment}"
            )

        input_dto.loaded_release_id = None
        return None

    async def _load_agent(self, uow: Any, input_dto: AskInput) -> Agent:
        runtime_session_mode = None
        if not self._is_network_runtime(input_dto):
            current_agent = await uow.agents.get_by_id(input_dto.agent_id)
            if current_agent is not None:
                runtime_session_mode = current_agent.session_mode

        loaded = await super()._load_agent(uow, input_dto)

        if runtime_session_mode is not None and not self._is_network_runtime(input_dto):
            loaded.session_mode = runtime_session_mode
        return loaded

    async def _resolve_session(self, session_repo: Any, input_dto: AskInput, agent: Agent):
        if self._is_network_runtime(input_dto):
            return await super()._resolve_session(session_repo, input_dto, agent)

        requested_session_id = input_dto.session_id
        session = await AskAgentUseCase._resolve_session(self, session_repo, input_dto, agent)
        environment = normalize_runtime_environment(input_dto.execution_context)
        existing = requested_session_id is not None
        if existing:
            session_environment = _session_environment(session)
            if session_environment != environment:
                raise ConflictError(
                    f"Agent Session belongs to {session_environment}, not {environment}"
                )
        else:
            session.runtime_environment = environment
            if environment == "draft":
                session.opened_release_id = None
            else:
                context = current_execution.get()
                session.opened_release_id = context.agent_release_id if context is not None else input_dto.loaded_release_id

        next_data = _clean_session_data(getattr(session, "data", None))
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        source = metadata.get("source")
        if isinstance(source, str) and source:
            next_data["source"] = source

        external_context = self._resolve_external_context(
            agent=agent,
            input_dto=input_dto,
            session=session,
        )

        changed = (
            next_data != (getattr(session, "data", None) or {})
            or external_context.session_changed
        )
        if not existing:
            changed = True
        session.data = next_data or None
        if changed:
            await session_repo.update(session)
        return session
