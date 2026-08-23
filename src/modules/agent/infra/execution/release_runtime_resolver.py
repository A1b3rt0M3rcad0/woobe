from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.execution.vector_snapshot_rag_mixin import VectorSnapshotRAGMixin
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import (
    tool_from_release_snapshot,
    tool_to_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.domain.entities import Agent, AgentRelease, ProviderModel
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus, ReleaseStatus, ToolStatus
from modules.agent.domain.errors import RuntimeEnvironmentNotReadyError
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from shared.contracts.errors import ConflictError, ValidationError
from shared.contracts.llm_cost import provider_model_pricing_snapshot
from shared.runtime_environment import normalize_runtime_environment


RuntimeToolReader = Callable[[list[UUID]], Awaitable[list[Any]]]


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _release_sort_key(release: AgentRelease) -> float:
    value = release.updated_at or release.created_at
    return value.timestamp() if value is not None else 0.0


def _session_data(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _session_release_id(data: dict[str, Any]) -> UUID | None:
    raw_release_id = data.get("loaded_release_id")
    if raw_release_id in (None, ""):
        return None
    try:
        return raw_release_id if isinstance(raw_release_id, UUID) else UUID(str(raw_release_id))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Agent Session contains an invalid release binding") from exc


class ReleaseRuntimeResolver(VectorSnapshotRAGMixin, AskAgentUseCase):
    _runtime_tool_reader: RuntimeToolReader | None = None

    def configure_runtime_tool_reader(self, reader: RuntimeToolReader) -> None:
        self._runtime_tool_reader = reader

    @staticmethod
    def _is_network_runtime(input_dto: AskInput) -> bool:
        metadata = input_dto.metadata
        return isinstance(metadata, dict) and metadata.get("source") == "network_runtime"

    async def _session_runtime_binding(self, uow: Any, input_dto: AskInput) -> UUID | None:
        if input_dto.session_id is None or self._is_network_runtime(input_dto):
            return None
        session_repo = getattr(uow, "sessions", None)
        if session_repo is None:
            return None
        try:
            session = await session_repo.get_by_id(input_dto.session_id)
        except Exception:
            return None
        if session.project_id != input_dto.project_id or session.agent_id != input_dto.agent_id:
            raise ValidationError("Agent Session does not belong to this Agent runtime")

        data = _session_data(session.data)
        if data.get("chat_surface_dynamic_release") is True:
            return None
        requested_environment = normalize_runtime_environment(input_dto.execution_context)
        raw_environment = data.get("runtime_environment")
        if raw_environment not in (None, ""):
            session_environment = normalize_runtime_environment(str(raw_environment))
            if session_environment != requested_environment:
                raise ConflictError(
                    f"Agent Session belongs to {session_environment}, not {requested_environment}"
                )

        bound_release_id = _session_release_id(data)
        if (
            bound_release_id is not None
            and input_dto.loaded_release_id is not None
            and bound_release_id != input_dto.loaded_release_id
        ):
            raise ConflictError("Agent Session is pinned to a different Release")
        return bound_release_id

    async def _resolve_session(self, session_repo: Any, input_dto: AskInput, agent: Agent):
        session = await super()._resolve_session(session_repo, input_dto, agent)
        if session is None or self._is_network_runtime(input_dto):
            return session

        environment = normalize_runtime_environment(input_dto.execution_context)
        data = _session_data(session.data)
        dynamic_release = data.get("chat_surface_dynamic_release") is True
        raw_environment = data.get("runtime_environment")
        if raw_environment not in (None, ""):
            session_environment = normalize_runtime_environment(str(raw_environment))
            if session_environment != environment:
                raise ConflictError(
                    f"Agent Session belongs to {session_environment}, not {environment}"
                )

        context = current_execution.get()
        resolved_release_id = input_dto.loaded_release_id
        resolved_release_version = None
        if context is not None:
            resolved_release_id = context.agent_release_id or resolved_release_id
            resolved_release_version = context.agent_release_version

        existing_release_id = _session_release_id(data)
        if (
            not dynamic_release
            and environment != "draft"
            and existing_release_id is not None
            and resolved_release_id is not None
            and existing_release_id != resolved_release_id
        ):
            raise ConflictError("Agent Session is pinned to a different Release")

        next_data = dict(data)
        next_data["runtime_environment"] = environment
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        source = metadata.get("source")
        if isinstance(source, str) and source:
            next_data["source"] = source

        if environment == "draft":
            next_data.pop("loaded_release_id", None)
            next_data.pop("release_version", None)
        elif resolved_release_id is not None and dynamic_release:
            next_data.pop("loaded_release_id", None)
            next_data.pop("release_version", None)
            next_data["last_release_id"] = str(resolved_release_id)
            if resolved_release_version:
                next_data["last_release_version"] = resolved_release_version
        elif resolved_release_id is not None:
            next_data["loaded_release_id"] = str(resolved_release_id)
            if resolved_release_version:
                next_data["release_version"] = resolved_release_version

        if next_data != data:
            session.data = next_data
            await session_repo.update(session)
        return session

    @staticmethod
    def _apply_runtime_config_snapshot(agent: Agent, runtime_config: Any) -> Agent:
        if runtime_config is None:
            return agent
        if not isinstance(runtime_config, dict):
            raise ValidationError("Agent runtime_config snapshot is invalid")
        settings = dict(agent.settings or {})
        settings["runtime_config"] = deepcopy(runtime_config)
        agent.settings = settings
        return agent

    @staticmethod
    def _snapshot_index(raw_snapshots: Any) -> dict[str, dict[str, Any]]:
        if raw_snapshots is None:
            return {}
        if not isinstance(raw_snapshots, list):
            raise ValidationError("Release contains invalid tool snapshots")

        result: dict[str, dict[str, Any]] = {}
        for raw_snapshot in raw_snapshots:
            if not isinstance(raw_snapshot, dict):
                raise ValidationError("Release contains an invalid tool snapshot")
            raw_id = raw_snapshot.get("id")
            if raw_id is None:
                raise ValidationError("Release tool snapshot id is missing")
            result[str(raw_id)] = raw_snapshot
        return result

    @staticmethod
    def _selected_tool_ids(raw_tool_ids: Any, raw_snapshots: Any) -> list[UUID]:
        ordered_ids: list[UUID] = []
        seen: set[UUID] = set()

        source_ids: list[Any]
        if isinstance(raw_tool_ids, list):
            source_ids = raw_tool_ids
        elif isinstance(raw_snapshots, list):
            source_ids = [
                snapshot.get("id")
                for snapshot in raw_snapshots
                if isinstance(snapshot, dict)
            ]
        else:
            source_ids = []

        for raw_tool_id in source_ids:
            try:
                tool_id = raw_tool_id if isinstance(raw_tool_id, UUID) else UUID(str(raw_tool_id))
            except (TypeError, ValueError) as exc:
                raise ValidationError("Draft contains an invalid tool id") from exc
            if tool_id in seen:
                continue
            seen.add(tool_id)
            ordered_ids.append(tool_id)
        return ordered_ids

    async def _prepare(self, input_dto: Any) -> Any:
        prepared = await super()._prepare(input_dto)
        if not isinstance(prepared, tuple) or len(prepared) < 13:
            return prepared
        return await self._apply_runtime_tool_selection(prepared)

    async def _apply_runtime_tool_selection(self, prepared: tuple[Any, ...]) -> tuple[Any, ...]:
        agent = prepared[0]
        settings = dict(getattr(agent, "settings", None) or {})
        runtime_config = settings.get("runtime_config")
        if not isinstance(runtime_config, dict):
            return prepared
        tools_config = runtime_config.get("tools")
        if not isinstance(tools_config, dict):
            return prepared

        raw_snapshots = tools_config.get("snapshots")
        raw_tool_ids = tools_config.get("tool_ids")
        raw_permissions = tools_config.get("permissions")
        permission_map = raw_permissions if isinstance(raw_permissions, dict) else {}
        snapshot_index = self._snapshot_index(raw_snapshots)
        selected_ids = self._selected_tool_ids(raw_tool_ids, raw_snapshots)

        snapshot_tools: dict[UUID, Any] = {}
        for tool_id in selected_ids:
            raw_snapshot = snapshot_index.get(str(tool_id))
            if raw_snapshot is None:
                continue
            tool = tool_from_release_snapshot(raw_snapshot)
            if tool.project_id != agent.project_id:
                raise ValidationError("Release tool snapshot does not belong to this Project")
            if _value(tool.status) != ToolStatus.ACTIVE.value:
                raise ValidationError(f"Release tool snapshot is not active: {tool.name}")
            snapshot_tools[tool_id] = tool

        live_ids = [tool_id for tool_id in selected_ids if tool_id not in snapshot_tools]
        live_tools: dict[UUID, Any] = {}
        if live_ids:
            if self._runtime_tool_reader is None:
                raise ValidationError("Draft Tool runtime reader is not configured")
            loaded_tools = await self._runtime_tool_reader(live_ids)
            live_tools = {tool.id: tool for tool in loaded_tools}

        tools = []
        snapshot_map: dict[str, dict[str, Any]] = {}
        snapshot_count = 0
        live_count = 0

        for tool_id in selected_ids:
            tool = snapshot_tools.get(tool_id)
            if tool is not None:
                snapshot_count += 1
            else:
                tool = live_tools.get(tool_id)
                if tool is None:
                    raise ValidationError(f"Selected tool was not found: {tool_id}")
                if tool.project_id != agent.project_id:
                    raise ValidationError("Selected tool does not belong to this Project")
                if _value(tool.status) != ToolStatus.ACTIVE.value:
                    raise ValidationError(f"Selected tool is not active: {tool.name}")
                live_count += 1

            effective_tool = tool_with_permission_overrides(
                tool,
                permission_map.get(str(tool_id)),
            )
            tools.append(effective_tool)
            snapshot_map[str(tool_id)] = tool_to_release_snapshot(effective_tool)

        if snapshot_count and live_count:
            source = "hybrid_snapshot"
        elif snapshot_count:
            source = "release_snapshot"
        else:
            source = "draft_live"

        definitions, name_to_id = agent_tools_to_openai_definitions_and_mapping(tools)
        context = current_execution.get()
        if context is not None:
            context.tool_snapshots = snapshot_map or None
            context.tool_metadata = {
                "source": source,
                "tool_ids": [str(tool.id) for tool in tools],
                "snapshot_hashes": [
                    snapshot.get("snapshot_hash")
                    for snapshot in snapshot_map.values()
                    if snapshot.get("snapshot_hash")
                ],
                "permission_overrides": permission_map or None,
            }

        mutable = list(prepared)
        mutable[7] = definitions
        mutable[8] = name_to_id
        mutable[9] = bool(definitions)
        return tuple(mutable)

    async def _merge_playground_runtime_config(
        self,
        release_repo: Any,
        agent_id: UUID,
        runtime_config: Any,
    ) -> Any:
        if not isinstance(runtime_config, dict) or release_repo is None:
            return runtime_config

        merged_runtime = deepcopy(runtime_config)
        tools_config = merged_runtime.get("tools")
        if not isinstance(tools_config, dict):
            return merged_runtime

        raw_tool_ids = tools_config.get("tool_ids")
        if not isinstance(raw_tool_ids, list):
            return merged_runtime

        selected_ids = [str(raw_tool_id) for raw_tool_id in raw_tool_ids]
        if not selected_ids:
            tools_config.pop("snapshots", None)
            return merged_runtime

        saved_snapshots: list[dict[str, Any]] = []
        drafts = await release_repo.list_by_status(agent_id, ReleaseStatus.draft)
        if drafts:
            current_draft = max(drafts, key=_release_sort_key)
            current_runtime = current_draft.runtime_config
            if isinstance(current_runtime, dict):
                current_tools = current_runtime.get("tools")
                if isinstance(current_tools, dict):
                    raw_saved_snapshots = current_tools.get("snapshots")
                    if isinstance(raw_saved_snapshots, list):
                        saved_snapshots = [
                            snapshot
                            for snapshot in raw_saved_snapshots
                            if isinstance(snapshot, dict)
                        ]

        snapshot_map: dict[str, dict[str, Any]] = {
            str(snapshot.get("id")): snapshot
            for snapshot in saved_snapshots
            if snapshot.get("id") is not None
        }
        explicit_snapshots = tools_config.get("snapshots")
        if isinstance(explicit_snapshots, list):
            for snapshot in explicit_snapshots:
                if isinstance(snapshot, dict) and snapshot.get("id") is not None:
                    snapshot_map[str(snapshot.get("id"))] = snapshot

        merged_snapshots = [
            deepcopy(snapshot_map[tool_id])
            for tool_id in selected_ids
            if tool_id in snapshot_map
        ]
        if merged_snapshots:
            tools_config["snapshots"] = merged_snapshots
        else:
            tools_config.pop("snapshots", None)
        return merged_runtime

    async def _load_agent(self, uow: Any, input_dto: AskInput) -> Agent:
        agent = await self._load_base_agent(uow, input_dto)
        release_repo = getattr(uow, "releases", None)
        execution_context = (input_dto.execution_context or "playground").lower()
        runtime_context = current_execution.get()
        if runtime_context is not None:
            runtime_context.execution_context = execution_context

        session_release_id = await self._session_runtime_binding(uow, input_dto)
        effective_release_id = session_release_id or input_dto.loaded_release_id

        if effective_release_id and release_repo is not None:
            release = await release_repo.get_by_id(effective_release_id)
            if release is None or release.agent_id != agent.id:
                raise ValidationError("Pinned Agent release was not found")
            input_dto.loaded_release_id = release.id
            self._bind_release_context(release)
            agent = self._apply_release_to_agent(agent, release)
            agent = self._apply_runtime_config_snapshot(agent, release.runtime_config)
            agent = self._apply_release_snapshot_ids(agent, release)
            return await self._resolve_provider_model_refs(uow, agent)

        if execution_context == "production":
            if release_repo is None:
                raise ValidationError("Production runtime requires release repository")
            release = await release_repo.get_active_production(agent.id)
            if release is None:
                raise RuntimeEnvironmentNotReadyError("production", input_dto.agent_id)
            input_dto.loaded_release_id = release.id
            self._bind_release_context(release)
            agent = self._apply_release_to_agent(agent, release)
            agent = self._apply_runtime_config_snapshot(agent, release.runtime_config)
            agent = self._apply_release_snapshot_ids(agent, release)
            return await self._resolve_provider_model_refs(uow, agent)

        if execution_context == "staging":
            if release_repo is None:
                raise ValidationError("Staging runtime requires release repository")
            releases = await release_repo.list_by_status(agent.id, ReleaseStatus.staging)
            if not releases:
                raise RuntimeEnvironmentNotReadyError("staging", input_dto.agent_id)
            release = max(releases, key=_release_sort_key)
            input_dto.loaded_release_id = release.id
            self._bind_release_context(release)
            agent = self._apply_release_to_agent(agent, release)
            agent = self._apply_runtime_config_snapshot(agent, release.runtime_config)
            agent = self._apply_release_snapshot_ids(agent, release)
            return await self._resolve_provider_model_refs(uow, agent)

        if execution_context != "playground":
            raise ValueError("Unsupported execution context")

        if input_dto.snapshot_override:
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

        if release_repo is not None:
            drafts = await release_repo.list_by_status(agent.id, ReleaseStatus.draft)
            if drafts:
                release = max(drafts, key=_release_sort_key)
                self._bind_release_context(release)
                agent = self._apply_release_to_agent(agent, release)
                agent = self._apply_runtime_config_snapshot(agent, release.runtime_config)
                agent = self._apply_release_snapshot_ids(agent, release)
                return await self._resolve_provider_model_refs(uow, agent)

        return await self._resolve_provider_model_refs(uow, agent)

    def _bind_release_context(self, release: AgentRelease) -> None:
        context = current_execution.get()
        if context is None:
            return
        context.agent_release_id = release.id
        context.agent_release_version = release.version

    async def _load_base_agent(self, uow: Any, input_dto: AskInput) -> Agent:
        from modules.agent.domain.errors import AgentNotFoundError

        agent = await uow.agents.get_by_id(input_dto.agent_id)
        if agent is None:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        status = getattr(agent, "status", None)
        status_value = getattr(status, "value", status)
        if status_value not in (None, "active"):
            raise ValidationError("Agent is not active")
        return agent

    def _apply_release_snapshot_ids(self, agent: Agent, release: AgentRelease) -> Agent:
        agent.provider_model_id = getattr(release, "provider_model_id", None) or agent.provider_model_id
        agent.fallback_provider_model_id = (
            getattr(release, "fallback_provider_model_id", None)
            or agent.fallback_provider_model_id
        )
        return agent

    def _apply_snapshot_provider_model_ids(self, agent: Agent, snapshot: dict) -> None:
        if snapshot.get("provider_model_id") is not None:
            value = snapshot["provider_model_id"]
            agent.provider_model_id = UUID(value) if isinstance(value, str) else value
        if snapshot.get("fallback_provider_model_id") is not None:
            value = snapshot["fallback_provider_model_id"]
            agent.fallback_provider_model_id = UUID(value) if isinstance(value, str) else value

    def _set_pricing_snapshot(
        self,
        agent: Agent,
        *,
        key: str,
        provider_model: ProviderModel,
        provider,
    ) -> None:
        settings = dict(agent.settings or {})
        settings[key] = provider_model_pricing_snapshot(
            provider_model_id=provider_model.id,
            provider_credential_id=provider_model.provider_credential_id,
            provider=provider,
            model=provider_model.model,
            metadata=provider_model.metadata,
        )
        agent.settings = settings

    def _validate_credential_runtime_status(self, credential) -> None:
        if getattr(credential.status, "value", credential.status) != CredentialStatus.active.value:
            raise ValidationError("Provider credential must be active")
        expires_at = (credential.metadata or {}).get("expires_at")
        if not expires_at:
            return
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError("Provider credential expiration date is invalid")
        if parsed <= datetime.now(timezone.utc):
            raise ValidationError("Provider credential has expired")

    async def _resolve_provider_model_refs(self, uow: Any, agent: Agent) -> Agent:
        provider_model_repo = getattr(uow, "provider_models", None)
        if provider_model_repo is None:
            self._validate_runtime_model(agent)
            return agent
        if agent.provider_model_id:
            provider_model = await provider_model_repo.get_by_id(agent.provider_model_id)
            if provider_model is None or provider_model.project_id != agent.project_id:
                from modules.agent.domain.errors import ModelConfigNotFoundError

                raise ModelConfigNotFoundError
            if getattr(provider_model.status, "value", provider_model.status) != ProviderModelStatus.active.value:
                raise ValidationError("Provider model must be active")
            credential = await uow.provider_credentials.get_by_id(provider_model.provider_credential_id)
            if credential is None or credential.project_id != agent.project_id:
                from modules.agent.domain.errors import CredentialNotFoundError

                raise CredentialNotFoundError(provider_model.provider_credential_id)
            self._validate_credential_runtime_status(credential)
            agent.provider_credential_id = credential.id
            agent.provider = credential.provider
            agent.model = provider_model.model
            self._set_pricing_snapshot(
                agent,
                key="model_pricing",
                provider_model=provider_model,
                provider=credential.provider,
            )

        if agent.fallback_provider_model_id:
            fallback_model = await provider_model_repo.get_by_id(agent.fallback_provider_model_id)
            if fallback_model is None or fallback_model.project_id != agent.project_id:
                from modules.agent.domain.errors import ModelConfigNotFoundError

                raise ModelConfigNotFoundError
            credential = await uow.provider_credentials.get_by_id(fallback_model.provider_credential_id)
            if credential is None or credential.project_id != agent.project_id:
                from modules.agent.domain.errors import CredentialNotFoundError

                raise CredentialNotFoundError(fallback_model.provider_credential_id)
            self._validate_credential_runtime_status(credential)
            agent.fallback_credential_id = credential.id
            agent.fallback_provider = credential.provider
            agent.fallback_model = fallback_model.model
            self._set_pricing_snapshot(
                agent,
                key="fallback_model_pricing",
                provider_model=fallback_model,
                provider=credential.provider,
            )

        self._validate_runtime_model(agent)
        return agent

    def _validate_runtime_model(self, agent: Agent) -> None:
        if not getattr(agent, "model", None):
            raise ValidationError("Agent model is not configured")
        if getattr(agent, "fallback_provider_model_id", None) and not getattr(agent, "fallback_model", None):
            raise ValidationError("Fallback provider model is not configured")
