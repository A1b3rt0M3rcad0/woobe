from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.messages import SystemMessage

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
    _messages_to_history,
)
from modules.agent.infra.execution.runtime_preparation import (
    prepare_project_environment_state,
    prepare_rag_binding,
    prepare_skill_state,
    prepare_tool_state,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    _TOOL_GROUNDING_RUNTIME_RULES,
)
from modules.agent.infra.execution.transaction_bounded_rag import (
    _rag_history_context,
)
from shared.contracts.errors import ConflictError, ValidationError
from shared.infra.crypto import decrypt_secret
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.runtime_environment import normalize_runtime_environment

logger = logging.getLogger(__name__)

RecoveryToolFromSnapshot = Callable[[dict[str, Any]], Any]
RecoveryToolWithPermissions = Callable[[Any, Any], Any]
RecoveryToolDefinitionBuilder = Callable[
    [list[Any]],
    tuple[list[dict[str, Any]], dict[str, str]],
]


def _uuid_or_none(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Agent Run recovery snapshot contains an invalid UUID") from exc


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


@dataclass(frozen=True, slots=True)
class AgentRunRecoveryRequest:
    """Trusted request to continue one already accepted standalone Agent Run."""

    run_id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID | None
    input_message_id: UUID | None
    trace_id: UUID
    agent_release_id: UUID | None
    environment: str
    input_message: str
    attempt: int
    checkpoint: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class _AcceptedRecoveryRun:
    run_id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID | None
    input_message_id: UUID | None
    trace_id: UUID
    agent_release_id: UUID | None
    environment: str
    input_message: str
    execution_snapshot: dict[str, Any]


class AgentRunRecoveryRuntime(FrozenSnapshotStructuredOutputRuntime):
    """Continue an existing Agent Run from its accepted immutable snapshot.

    This runtime is intentionally separate from the public execution path. It never
    creates a new AgentRun, never persists a second user message, and never emits the
    Acceptance outbox pair. The existing Run identity is supplied through the
    RequestExecutionContext by AgentRunRecoveryExecutor.
    """

    _recovery_tool_from_snapshot: RecoveryToolFromSnapshot | None = None
    _recovery_tool_with_permissions: RecoveryToolWithPermissions | None = None
    _recovery_tool_definition_builder: RecoveryToolDefinitionBuilder | None = None

    def configure_recovery_tool_runtime(
        self,
        *,
        tool_from_snapshot: RecoveryToolFromSnapshot,
        tool_with_permissions: RecoveryToolWithPermissions,
        tool_definition_builder: RecoveryToolDefinitionBuilder,
    ) -> None:
        """Inject Tool materialization owned by the composition boundary."""
        self._recovery_tool_from_snapshot = tool_from_snapshot
        self._recovery_tool_with_permissions = tool_with_permissions
        self._recovery_tool_definition_builder = tool_definition_builder

    def _require_recovery_tool_runtime(
        self,
    ) -> tuple[
        RecoveryToolFromSnapshot,
        RecoveryToolWithPermissions,
        RecoveryToolDefinitionBuilder,
    ]:
        if (
            self._recovery_tool_from_snapshot is None
            or self._recovery_tool_with_permissions is None
            or self._recovery_tool_definition_builder is None
        ):
            raise RuntimeError("Agent Run recovery Tool runtime is not configured")
        return (
            self._recovery_tool_from_snapshot,
            self._recovery_tool_with_permissions,
            self._recovery_tool_definition_builder,
        )

    @staticmethod
    def _validate_recovery_source(input_dto: AskInput) -> None:
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        if metadata.get("source") != "run_recovery":
            raise ValidationError("Agent Run recovery runtime accepts only internal recovery requests")

    @staticmethod
    def _validate_run_identity(run: Any, input_dto: AskInput, context: Any) -> None:
        status = str(_value(getattr(run, "status", None)) or "")
        if status != "running":
            raise ConflictError("Agent Run is no longer running")
        if str(getattr(run, "storage_version", "") or "") != EVENT_JOURNAL_STORAGE_VERSION:
            raise ConflictError("Agent Run is not owned by the event journal")
        if getattr(run, "network_execution_id", None) is not None or getattr(
            run, "network_invocation_id", None
        ) is not None:
            raise ConflictError("Network child Runs cannot use standalone recovery")
        if run.project_id != input_dto.project_id or run.agent_id != input_dto.agent_id:
            raise ConflictError("Agent Run recovery identity does not match the accepted Run")
        if run.id != context.run_id or run.trace_id != context.trace_id:
            raise ConflictError("Agent Run recovery canonical identity changed")
        if run.session_id != input_dto.session_id or run.session_id != context.session_id:
            raise ConflictError("Agent Run recovery Session does not match the accepted Run")
        if run.input_message_id != context.input_message_id:
            raise ConflictError("Agent Run recovery input provenance changed")
        if run.agent_release_id != context.agent_release_id:
            raise ConflictError("Agent Run recovery Release does not match the accepted Run")
        if run.input_message != input_dto.message:
            raise ConflictError("Agent Run recovery input does not match the accepted Run")
        if normalize_runtime_environment(run.environment) != normalize_runtime_environment(
            input_dto.execution_context
        ):
            raise ConflictError("Agent Run recovery environment changed")

    @classmethod
    def _accepted_snapshot(cls, run: Any) -> _AcceptedRecoveryRun:
        snapshot = deepcopy(getattr(run, "execution_snapshot", None) or {})
        if not isinstance(snapshot.get("agent"), dict):
            raise ValidationError("Agent Run has no reusable accepted execution snapshot")
        return _AcceptedRecoveryRun(
            run_id=run.id,
            project_id=run.project_id,
            agent_id=run.agent_id,
            session_id=run.session_id,
            input_message_id=run.input_message_id,
            trace_id=run.trace_id,
            agent_release_id=run.agent_release_id,
            environment=run.environment,
            input_message=run.input_message,
            execution_snapshot=snapshot,
        )

    @staticmethod
    def _apply_accepted_snapshot(agent: Any, accepted: _AcceptedRecoveryRun, context: Any) -> Any:
        snapshot = accepted.execution_snapshot
        raw_agent = snapshot.get("agent")
        if not isinstance(raw_agent, dict):
            raise ValidationError("Agent Run accepted snapshot has no Agent configuration")
        snapshot_agent_id = _uuid_or_none(raw_agent.get("id"))
        if snapshot_agent_id is not None and snapshot_agent_id != accepted.agent_id:
            raise ConflictError("Agent Run accepted snapshot belongs to another Agent")

        settings = deepcopy(raw_agent.get("settings") or {})
        if not isinstance(settings, dict):
            raise ValidationError("Agent Run accepted Agent settings are invalid")
        runtime_config = deepcopy(settings.get("runtime_config") or {})
        if not isinstance(runtime_config, dict):
            raise ValidationError("Agent Run accepted runtime_config is invalid")

        raw_tools = snapshot.get("tools")
        if isinstance(raw_tools, list):
            tool_snapshots = [deepcopy(item) for item in raw_tools if isinstance(item, dict)]
            tools_config = deepcopy(runtime_config.get("tools") or {})
            if not isinstance(tools_config, dict):
                tools_config = {}
            tools_config["snapshots"] = tool_snapshots
            tools_config["tool_ids"] = [
                str(item["id"])
                for item in tool_snapshots
                if item.get("id") not in {None, ""}
            ]
            runtime_config["tools"] = tools_config
            context.tool_snapshots = {
                str(item["id"]): deepcopy(item)
                for item in tool_snapshots
                if item.get("id") not in {None, ""}
            } or None

        raw_knowledge = snapshot.get("knowledge")
        if isinstance(raw_knowledge, dict) and raw_knowledge.get("knowledge_version_id"):
            settings["knowledge_version_id"] = str(raw_knowledge["knowledge_version_id"])
        settings["runtime_config"] = runtime_config

        if raw_agent.get("name") is not None:
            agent.name = raw_agent["name"]
        if raw_agent.get("description") is not None:
            agent.description = raw_agent["description"]
        agent.behavior_spec = deepcopy(raw_agent.get("behavior_spec"))
        agent.system_prompt = str(raw_agent.get("system_prompt") or "")

        provider = raw_agent.get("provider")
        model = raw_agent.get("model")
        session_mode = raw_agent.get("session_mode")
        if not provider or not model:
            raise ValidationError("Agent Run accepted snapshot has no executable model")
        if session_mode not in {SessionMode.stateful.value, SessionMode.stateless.value}:
            raise ValidationError("Agent Run accepted snapshot has invalid Session Mode")
        agent.provider = Provider(str(provider))
        agent.model = str(model)
        agent.provider_model_id = _uuid_or_none(raw_agent.get("provider_model_id"))
        agent.provider_credential_id = _uuid_or_none(raw_agent.get("provider_credential_id"))

        fallback_provider = raw_agent.get("fallback_provider")
        agent.fallback_provider = Provider(str(fallback_provider)) if fallback_provider else None
        agent.fallback_model = raw_agent.get("fallback_model")
        agent.fallback_provider_model_id = _uuid_or_none(
            raw_agent.get("fallback_provider_model_id")
        )
        agent.fallback_credential_id = _uuid_or_none(raw_agent.get("fallback_credential_id"))
        agent.temperature = raw_agent.get("temperature")
        agent.max_output_tokens = raw_agent.get("max_output_tokens")
        agent.session_mode = SessionMode(str(session_mode))
        agent.settings = settings

        release = snapshot.get("release")
        if isinstance(release, dict):
            release_id = _uuid_or_none(release.get("id"))
            if release_id != accepted.agent_release_id:
                raise ConflictError("Agent Run accepted Release snapshot changed")
            context.agent_release_version = (
                str(release.get("version"))
                if release.get("version") not in {None, ""}
                else None
            )
        return agent

    async def _read_accepted_run(self, input_dto: AskInput) -> _AcceptedRecoveryRun:
        context = current_execution.get()
        if context is None or context.run_id is None or context.trace_id is None:
            raise RuntimeError("Agent Run recovery has no trusted execution context")

        async def read_run(repositories, _outbox):
            run = await repositories.runs.get_by_id(context.run_id)
            if run is None:
                raise ConflictError("Agent Run no longer exists")
            self._validate_run_identity(run, input_dto, context)
            return self._accepted_snapshot(run)

        return await self._transactions.read(read_run)

    async def _prepare_recovery_material(
        self,
        accepted: _AcceptedRecoveryRun,
        input_dto: AskInput,
    ) -> tuple[Any, ...]:
        context = current_execution.get()
        if context is None:
            raise RuntimeError("Agent Run recovery context disappeared")
        (
            tool_from_snapshot,
            tool_with_permissions,
            tool_definition_builder,
        ) = self._require_recovery_tool_runtime()

        async def read_prepare(repositories, _outbox):
            run = await repositories.runs.get_by_id(accepted.run_id)
            if run is None:
                raise ConflictError("Agent Run no longer exists")
            self._validate_run_identity(run, input_dto, context)

            agent = await repositories.agents.get_by_id(accepted.agent_id)
            if agent is None or agent.project_id != accepted.project_id:
                raise ConflictError("Accepted Agent is no longer available in this Project")
            agent = self._apply_accepted_snapshot(agent, accepted, context)

            primary_credential = await self._load_credential(
                repositories.provider_credentials,
                agent,
            )
            fallback_credential = None
            if agent.fallback_credential_id:
                fallback_credential = await repositories.provider_credentials.get_by_id(
                    agent.fallback_credential_id
                )
                if fallback_credential is None:
                    raise ValidationError("Accepted fallback credential was not found")

            tools, encrypted_tool_secrets = await prepare_tool_state(
                repositories,
                agent=agent,
                tool_from_snapshot=tool_from_snapshot,
                tool_with_permissions=tool_with_permissions,
            )
            prepared_project_environment = await prepare_project_environment_state(
                repositories,
                project_id=accepted.project_id,
                environment=accepted.environment,
                tools=tools,
            )
            await prepare_skill_state(repositories, agent=agent)
            rag_binding = await prepare_rag_binding(repositories, agent=agent)

            session = None
            history: list[Any] = []
            if accepted.session_id is not None:
                session = await repositories.sessions.get_by_id(accepted.session_id)
                if (
                    session is None
                    or session.project_id != accepted.project_id
                    or session.agent_id != accepted.agent_id
                ):
                    raise ConflictError("Accepted Agent Session is no longer available")
                if accepted.input_message_id is None:
                    raise ValidationError("Accepted stateful Agent Run has no input message provenance")
                messages = list(await repositories.messages.list_by_session(session.id))
                source_index = next(
                    (
                        index
                        for index, message in enumerate(messages)
                        if getattr(message, "id", None) == accepted.input_message_id
                    ),
                    None,
                )
                if source_index is None:
                    raise ConflictError("Accepted Agent Run input message is no longer available")
                source_message = messages[source_index]
                if (
                    getattr(source_message, "session_id", None) != session.id
                    or getattr(source_message, "content", None) != accepted.input_message
                ):
                    raise ConflictError("Accepted Agent Run input message provenance changed")
                history = _messages_to_history(messages[:source_index])

            response_format = self._get_response_format(agent)
            json_enabled = (
                response_format.get("enabled", False)
                and response_format.get("type") == "json"
            )
            definitions, name_to_id = (
                tool_definition_builder(tools)
                if tools
                else ([], {})
            )
            return (
                agent,
                session,
                primary_credential,
                fallback_credential,
                tools,
                encrypted_tool_secrets,
                prepared_project_environment,
                rag_binding,
                history,
                response_format,
                json_enabled,
                definitions,
                name_to_id,
            )

        return await self._transactions.read(read_prepare)

    async def _prepare(self, input_dto: AskInput):
        self._validate_recovery_source(input_dto)
        context = current_execution.get()
        if (
            context is None
            or context.run_id is None
            or context.trace_id is None
            or context.storage_version != EVENT_JOURNAL_STORAGE_VERSION
            or context.run_attempt < 2
        ):
            raise RuntimeError("Agent Run recovery context is incomplete")

        accepted = await self._read_accepted_run(input_dto)
        context.project_id = accepted.project_id
        context.agent_id = accepted.agent_id
        context.session_id = accepted.session_id
        context.input_message_id = accepted.input_message_id
        context.agent_release_id = accepted.agent_release_id
        context.execution_context = accepted.environment

        await self._bind_durable_run_recorder(
            input_dto=input_dto,
            agent=type("AcceptedAgentIdentity", (), {"id": accepted.agent_id})(),
            session=(
                type("AcceptedSessionIdentity", (), {"id": accepted.session_id})()
                if accepted.session_id is not None
                else None
            ),
            trace_id=accepted.trace_id,
            run_id=accepted.run_id,
            execution_snapshot=accepted.execution_snapshot,
        )

        rag_token = _rag_history_context.set([])
        try:
            try:
                (
                    agent,
                    session,
                    primary_credential,
                    fallback_credential,
                    tools,
                    encrypted_tool_secrets,
                    prepared_project_environment,
                    rag_binding,
                    history,
                    response_format,
                    json_enabled,
                    definitions,
                    name_to_id,
                ) = await self._prepare_recovery_material(accepted, input_dto)

                _rag_history_context.set(history)
                api_key = self._decrypt_api_key(primary_credential)
                base_url = self._resolve_base_url(agent, primary_credential)
                fallback_data = None
                if fallback_credential is not None:
                    fallback_provider = _value(agent.fallback_provider)
                    fallback_data = {
                        "api_key": self._decrypt_api_key(fallback_credential),
                        "base_url": self._resolve_base_url_for_provider(
                            fallback_provider,
                            fallback_credential,
                            agent.settings,
                        ),
                    }
                tool_secrets = {
                    name: decrypt_secret(ciphertext, self._encryption_key)
                    for name, ciphertext in encrypted_tool_secrets.items()
                }
                context.prepared_fallback = fallback_data
                context.prepared_tools = {str(tool.id): tool for tool in tools}
                context.prepared_tool_secrets = tool_secrets
                context.prepared_project_environment = prepared_project_environment
                context.prepared_rag = rag_binding
                context.tool_metadata = {
                    "source": "accepted_run_snapshot",
                    "tool_ids": [str(tool.id) for tool in tools],
                }

                if self._execution_state_store is not None:
                    await self._execution_state_store.create(
                        accepted.run_id,
                        {
                            "status": "running",
                            "phase": "recovered",
                            "project_id": str(accepted.project_id),
                            "agent_id": str(accepted.agent_id),
                            "session_id": str(accepted.session_id) if accepted.session_id else None,
                            "trace_id": str(accepted.trace_id),
                            "environment": normalize_runtime_environment(accepted.environment),
                            "attempt": context.run_attempt,
                            "storage_version": EVENT_JOURNAL_STORAGE_VERSION,
                            "recovered": True,
                        },
                        ttl_seconds=self._execution_state_ttl_seconds,
                    )
                    await self._execution_state_store.append_event(
                        accepted.run_id,
                        "agent.run.recovered",
                        {"attempt": context.run_attempt, "trace_id": str(accepted.trace_id)},
                    )

                rag_context, sources = await self._load_rag_context(
                    agent,
                    accepted.input_message,
                    self._transactions,
                )
                if context.run_event_recorder is not None and sources:
                    await context.run_event_recorder.emit(
                        "knowledge.retrieval.completed",
                        {
                            "source_count": len(sources),
                            "sources": [
                                source.model_dump() if hasattr(source, "model_dump") else source
                                for source in sources
                            ],
                        },
                    )
                context.context_rag_sources = [
                    source.model_dump() if hasattr(source, "model_dump") else dict(source)
                    for source in sources or []
                    if hasattr(source, "model_dump") or isinstance(source, dict)
                ]
                messages = self._build_messages(
                    agent,
                    rag_context,
                    history,
                    accepted.input_message,
                    response_format if json_enabled else None,
                )
                if definitions:
                    insert_at = len(messages) - 1 if messages else 0
                    messages.insert(
                        insert_at,
                        SystemMessage(content=_TOOL_GROUNDING_RUNTIME_RULES),
                    )
                await self._hot_update(
                    {"phase": "llm", "rag_sources": len(sources or [])}
                )
                return (
                    agent,
                    session,
                    accepted.trace_id,
                    api_key,
                    base_url,
                    response_format,
                    json_enabled,
                    definitions,
                    name_to_id,
                    bool(definitions),
                    sources,
                    messages,
                    history,
                )
            except Exception as exc:
                await self._persist_prepare_failure(input_dto, exc)
                raise
        finally:
            _rag_history_context.reset(rag_token)


class AgentRunRecoveryExecutor:
    """Trusted host adapter that installs the existing Run identity before execute()."""

    def __init__(self, runtime: AgentRunRecoveryRuntime) -> None:
        self._runtime = runtime

    async def execute(self, request: AgentRunRecoveryRequest) -> AskOutput:
        if request.attempt < 2:
            raise ValidationError("Agent Run recovery Attempt must be greater than one")

        context = new_execution_context()
        context.run_id = request.run_id
        context.project_id = request.project_id
        context.agent_id = request.agent_id
        context.session_id = request.session_id
        context.input_message_id = request.input_message_id
        context.trace_id = request.trace_id
        context.agent_release_id = request.agent_release_id
        context.execution_context = request.environment
        context.storage_version = EVENT_JOURNAL_STORAGE_VERSION
        context.run_attempt = request.attempt
        context.resume_state = deepcopy(request.checkpoint) if request.checkpoint is not None else None
        if isinstance(request.checkpoint, dict):
            raw_context_manager_state = request.checkpoint.get("context_manager_state")
            if isinstance(raw_context_manager_state, dict):
                context.context_manager_state = deepcopy(raw_context_manager_state)

        input_dto = AskInput(
            project_id=request.project_id,
            agent_id=request.agent_id,
            message=request.input_message,
            session_id=request.session_id,
            metadata={
                "source": "run_recovery",
                "recovery_attempt": request.attempt,
            },
            execution_context=request.environment,
            loaded_release_id=request.agent_release_id,
        )
        token = current_execution.set(context)
        try:
            return await self._runtime.execute(input_dto)
        finally:
            current_execution.reset(token)