from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.vector_snapshot_rag_mixin import VectorSnapshotRAGMixin
from modules.agent.domain.entities import Agent, AgentRelease, ProviderModel
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus, ReleaseStatus, ToolStatus
from shared.infra.errors import ValidationError
from shared.infra.llm_cost import provider_model_pricing_snapshot


RuntimeToolReader = Callable[[list[UUID]], Awaitable[list[Any]]]


def _value(value: object) -> object:
    return getattr(value, "value", value)


class ReleaseRuntimeResolver(VectorSnapshotRAGMixin, AskAgentUseCase):
    _runtime_tool_reader: RuntimeToolReader | None = None

    def configure_runtime_tool_reader(self, reader: RuntimeToolReader) -> None:
        self._runtime_tool_reader = reader

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

        tools = []
        snapshot_map: dict[str, dict[str, Any]] = {}
        source = "draft_live"
        raw_snapshots = tools_config.get("snapshots")
        raw_tool_ids = tools_config.get("tool_ids")

        if isinstance(raw_snapshots, list) and raw_snapshots:
            source = "release_snapshot"
            for raw_snapshot in raw_snapshots:
                if not isinstance(raw_snapshot, dict):
                    raise ValidationError("Release contains an invalid tool snapshot")
                tool = tool_from_release_snapshot(raw_snapshot)
                if tool.project_id != agent.project_id:
                    raise ValidationError("Release tool snapshot does not belong to this Project")
                if _value(tool.status) != ToolStatus.ACTIVE.value:
                    raise ValidationError(f"Release tool snapshot is not active: {tool.name}")
                tools.append(tool)
                snapshot_map[str(tool.id)] = dict(raw_snapshot)
        elif isinstance(raw_tool_ids, list):
            seen: set[UUID] = set()
            selected_ids: list[UUID] = []
            for raw_tool_id in raw_tool_ids:
                try:
                    tool_id = raw_tool_id if isinstance(raw_tool_id, UUID) else UUID(str(raw_tool_id))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("Draft contains an invalid tool id") from exc
                if tool_id in seen:
                    continue
                seen.add(tool_id)
                selected_ids.append(tool_id)

            if selected_ids:
                if self._runtime_tool_reader is None:
                    raise ValidationError("Draft Tool runtime reader is not configured")
                loaded_tools = await self._runtime_tool_reader(selected_ids)
                tools_by_id = {tool.id: tool for tool in loaded_tools}
                for tool_id in selected_ids:
                    tool = tools_by_id.get(tool_id)
                    if tool is None:
                        raise ValidationError(f"Selected tool was not found: {tool_id}")
                    if tool.project_id != agent.project_id:
                        raise ValidationError("Selected tool does not belong to this Project")
                    if _value(tool.status) != ToolStatus.ACTIVE.value:
                        raise ValidationError(f"Selected tool is not active: {tool.name}")
                    tools.append(tool)

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
            }

        mutable = list(prepared)
        mutable[7] = definitions
        mutable[8] = name_to_id
        mutable[9] = bool(definitions)
        return tuple(mutable)

    async def _load_agent(self, uow: Any, input_dto: AskInput) -> Agent:
        agent = await self._load_base_agent(uow, input_dto)
        release_repo = getattr(uow, "releases", None)
        execution_context = (input_dto.execution_context or "playground").lower()
        runtime_context = current_execution.get()
        if runtime_context is not None:
            runtime_context.execution_context = execution_context

        if execution_context == "production":
            if release_repo is None:
                raise ValidationError("Production runtime requires release repository")
            release = await release_repo.get_active_production(agent.id)
            if release is None:
                raise ValidationError(f"No production release deployed for agent {input_dto.agent_id}")
            self._bind_release_context(release)
            agent = self._apply_release_snapshot_ids(
                self._apply_release_to_agent(agent, release),
                release,
            )
            return await self._resolve_provider_model_refs(uow, agent)

        if execution_context == "staging":
            if release_repo is None:
                raise ValidationError("Staging runtime requires release repository")
            releases = await release_repo.list_by_status(agent.id, ReleaseStatus.staging)
            if not releases:
                raise ValidationError(f"No staging release deployed for agent {input_dto.agent_id}")
            release = releases[0]
            self._bind_release_context(release)
            agent = self._apply_release_snapshot_ids(
                self._apply_release_to_agent(agent, release),
                release,
            )
            return await self._resolve_provider_model_refs(uow, agent)

        if execution_context != "playground":
            raise ValueError("Unsupported execution context")

        if input_dto.snapshot_override:
            agent = self._apply_snapshot_override(agent, input_dto.snapshot_override)
            self._apply_snapshot_provider_model_ids(agent, input_dto.snapshot_override)
            return await self._resolve_provider_model_refs(uow, agent)

        if input_dto.loaded_release_id and release_repo is not None:
            release = await release_repo.get_by_id(input_dto.loaded_release_id)
            if release is not None:
                self._bind_release_context(release)
                agent = self._apply_release_snapshot_ids(
                    self._apply_release_to_agent(agent, release),
                    release,
                )
                return await self._resolve_provider_model_refs(uow, agent)

        if release_repo is not None:
            drafts = await release_repo.list_by_status(agent.id, ReleaseStatus.draft)
            if drafts:
                release = drafts[0]
                self._bind_release_context(release)
                agent = self._apply_release_snapshot_ids(
                    self._apply_release_to_agent(agent, release),
                    release,
                )
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
