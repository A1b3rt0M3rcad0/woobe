from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput, SourceInfo
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.interfaces.run_persistence import AgentRunPersistencePort
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import (
    tool_from_release_snapshot,
    tool_to_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionFailedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionRequestedV1,
    AgentExecutionStartedV1,
    AgentExecutionToolCompletedV1,
    AgentFallbackTriggeredV1,
)
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.agent.infra.execution.runtime_preparation import prepare_skill_state
from modules.agent.infra.execution.runtime_preparation import (
    build_execution_snapshot,
    prepare_project_environment_state,
    prepare_rag_binding,
    prepare_tool_state,
    prefer_live_tools_for_run,
)
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from shared.contracts.execution_state import ExecutionStateStore
from shared.contracts.run_event_buffer import RunEventBufferPort
from shared.infra.crypto import decrypt_secret
from shared.runtime.durability import RunDurabilityBarrier
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION, LEGACY_STORAGE_VERSION
from shared.runtime.journal_recorder import DurableRunEventRecorder
from shared.runtime_environment import normalize_runtime_environment

logger = logging.getLogger(__name__)


class ExplicitRuntimePersistenceMixin:
    """Durable Acceptance plus a selectable legacy or event-journal terminal strategy."""

    _execution_state_store: ExecutionStateStore | None = None
    _execution_state_ttl_seconds = 3600
    _execution_terminal_ttl_seconds = 900
    _run_persistence: AgentRunPersistencePort | None = None
    _run_event_buffer: RunEventBufferPort | None = None
    _run_durability_barrier: RunDurabilityBarrier | None = None

    def configure_execution_state_store(
        self,
        store: ExecutionStateStore,
        *,
        ttl_seconds: int = 3600,
        terminal_ttl_seconds: int = 900,
    ) -> None:
        self._execution_state_store = store
        self._execution_state_ttl_seconds = ttl_seconds
        self._execution_terminal_ttl_seconds = terminal_ttl_seconds

    def configure_run_persistence(self, persistence: AgentRunPersistencePort) -> None:
        self._run_persistence = persistence

    def configure_run_event_journal(
        self,
        buffer: RunEventBufferPort,
        barrier: RunDurabilityBarrier,
    ) -> None:
        self._run_event_buffer = buffer
        self._run_durability_barrier = barrier

    def _storage_version(self) -> str:
        persistence = self._run_persistence
        return persistence.storage_version if persistence is not None else LEGACY_STORAGE_VERSION

    async def _bind_durable_run_recorder(
        self,
        *,
        input_dto: AskInput,
        agent: Any,
        session: Any,
        trace_id: UUID,
        run_id: UUID,
        execution_snapshot: dict[str, Any],
    ) -> None:
        context = current_execution.get()
        storage_version = self._storage_version()
        if context is not None:
            context.storage_version = storage_version
        if storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            return
        if context is None or self._run_event_buffer is None or self._run_durability_barrier is None:
            raise RuntimeError("event_journal Agent Run is missing durable journal dependencies")
        recorder = DurableRunEventRecorder(
            buffer=self._run_event_buffer,
            barrier=self._run_durability_barrier,
            run_id=run_id,
            run_kind="agent",
            session_id=session.id,
            metadata={
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "trace_id": str(trace_id),
                "network_execution_id": (
                    str(context.network_execution_id)
                    if context.network_execution_id
                    else None
                ),
                "invocation_id": (
                    str(context.network_invocation_id)
                    if context.network_invocation_id
                    else None
                ),
                "visibility": "internal",
            },
            attempt=context.run_attempt,
        )
        context.run_event_recorder = recorder
        await recorder.emit(
            "run.attempt.started",
            {
                "attempt": context.run_attempt,
                "environment": normalize_runtime_environment(input_dto.execution_context),
                "origin": str((input_dto.metadata or {}).get("source") or "runtime_api"),
                "input_message": input_dto.message,
                "execution_snapshot": execution_snapshot,
                "agent_release_id": str(context.agent_release_id) if context.agent_release_id else None,
                "agent_release_version": context.agent_release_version,
            },
            durable=True,
        )
        await recorder.emit(
            "execution.started",
            {"attempt": context.run_attempt},
        )

    async def _hot_update(self, values: dict[str, Any]) -> None:
        context = current_execution.get()
        if context is None or context.run_id is None or self._execution_state_store is None:
            return
        await self._execution_state_store.update(context.run_id, values)

    async def _hot_terminal_pending(
        self,
        *,
        terminal_status: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "status": "terminal_pending_persist",
            "terminal_status": terminal_status,
            "phase": "terminal_event",
        }
        if result is not None:
            payload["terminal_result"] = result
        await self._hot_update(payload)

    async def _hot_persisted(self, status: str) -> None:
        context = current_execution.get()
        if context is None or context.run_id is None or self._execution_state_store is None:
            return
        await self._execution_state_store.update(
            context.run_id,
            {"status": status, "phase": "persisted"},
        )
        await self._execution_state_store.expire(
            context.run_id,
            ttl_seconds=self._execution_terminal_ttl_seconds,
        )

    async def _persist_prepare_failure(
        self,
        input_dto: AskInput,
        error: Exception,
    ) -> None:
        context = current_execution.get()
        if context is None or context.run_id is None or context.terminal_persisted:
            return
        persistence = self._run_persistence
        if persistence is not None:
            try:
                handled = await persistence.prepare_failure(
                    self,
                    input_dto=input_dto,
                    error=error,
                )
                if handled:
                    return
            except Exception as persistence_error:
                logger.warning(
                    "Failed to persist Agent Run prepare failure through %s: %s",
                    persistence.storage_version,
                    persistence_error,
                )
                if persistence.storage_version != LEGACY_STORAGE_VERSION:
                    raise
        await self._persist_prepare_failure_legacy(input_dto, error)

    async def _persist_prepare_failure_legacy(
        self,
        input_dto: AskInput,
        error: Exception,
    ) -> None:
        context = current_execution.get()
        if context is None or context.run_id is None or context.terminal_persisted:
            return

        run_id = context.run_id
        trace_id = context.trace_id
        error_text = str(error)
        result = {
            "run_id": str(run_id),
            "trace_id": str(trace_id) if trace_id else None,
            "project_id": str(input_dto.project_id),
            "agent_id": str(context.agent_id or input_dto.agent_id),
            "session_id": str(context.session_id) if context.session_id else None,
            "error": error_text,
            "failure_phase": "prepare",
        }

        try:
            await self._hot_terminal_pending(
                terminal_status="failed",
                result=result,
            )
        except Exception as hot_state_error:
            logger.warning(
                "Failed to mark Agent Run terminal_pending_persist after prepare failure: %s",
                hot_state_error,
            )

        async def persist_failure(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> bool:
            run = await repositories.runs.get_by_id(run_id)
            if run is None or run.status != AgentRunStatus.RUNNING:
                return False

            await outbox.write(
                AgentExecutionFailedV1.create(
                    agent_id=context.agent_id or input_dto.agent_id,
                    session_id=context.session_id or trace_id or input_dto.agent_id,
                    payload=result,
                )
            )
            run.status = AgentRunStatus.FAILED
            run.failure_code = "prepare_failed"
            run.failure_detail = error_text[:8000]
            run.result = result
            run.completed_at = datetime.now(timezone.utc)
            await repositories.runs.save(run)
            return True

        try:
            persisted = await self._transactions.run(persist_failure)
        except Exception as persistence_error:
            logger.warning(
                "Failed to persist Agent Run prepare failure: %s",
                persistence_error,
            )
            return

        if not persisted:
            return

        context.terminal_persisted = True
        try:
            await self._hot_persisted("failed")
        except Exception as hot_state_error:
            logger.warning(
                "Failed to mark Agent Run failed in execution state: %s",
                hot_state_error,
            )

    async def _prepare(self, input_dto: AskInput):
        async def accept_run(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ):
            trace_id = uuid4()
            context = current_execution.get()
            metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
            source = str(metadata.get("source") or "runtime_api")
            environment = normalize_runtime_environment(input_dto.execution_context)

            if source != "network_runtime":
                await repositories.environment.assert_enabled(
                    agent_id=input_dto.agent_id,
                    project_id=input_dto.project_id,
                    environment=environment,
                )

            agent = await self._load_agent(repositories, input_dto)
            primary_credential = await self._load_credential(
                repositories.provider_credentials,
                agent,
            )
            fallback_credential = None
            if agent.fallback_credential_id:
                fallback_credential = await repositories.provider_credentials.get_by_id(
                    agent.fallback_credential_id
                )

            tools, encrypted_tool_secrets = await prepare_tool_state(
                repositories,
                agent=agent,
                tool_from_snapshot=tool_from_release_snapshot,
                tool_with_permissions=tool_with_permission_overrides,
                prefer_live_tools=prefer_live_tools_for_run(input_dto),
            )
            prepared_project_environment = await prepare_project_environment_state(
                repositories,
                project_id=input_dto.project_id,
                environment=environment,
                tools=tools,
            )
            await prepare_skill_state(repositories, agent=agent)
            rag_binding = await prepare_rag_binding(repositories, agent=agent)

            response_format = self._get_response_format(agent)
            json_enabled = (
                response_format.get("enabled", False)
                and response_format.get("type") == "json"
            )
            agent_tools, tool_name_to_id = (
                agent_tools_to_openai_definitions_and_mapping(tools)
                if tools
                else ([], {})
            )

            session = await self._resolve_session(repositories.sessions, input_dto, agent)
            history = (
                await self._load_history(repositories.messages, session)
                if self._uses_session_history(agent) else []
            )
            input_message_id = None
            if session:
                created_user = await self._save_user_message(
                    repositories.sessions,
                    repositories.messages,
                    session,
                    input_dto.message,
                    agent,
                )
                input_message_id = getattr(created_user, "id", None)

            release_id = (
                context.agent_release_id
                if context and context.agent_release_id
                else input_dto.loaded_release_id
            )
            release_version = context.agent_release_version if context else None
            rerun_of_run_id = metadata.get("rerun_of_run_id")
            if rerun_of_run_id and not isinstance(rerun_of_run_id, UUID):
                rerun_of_run_id = UUID(str(rerun_of_run_id))
            execution_snapshot = build_execution_snapshot(
                agent=agent,
                tools=tools,
                rag_binding=rag_binding,
                release_id=release_id,
                release_version=release_version,
                tool_to_snapshot=tool_to_release_snapshot,
            )

            run = await repositories.runs.create(
                AgentRun(
                    project_id=input_dto.project_id,
                    agent_id=agent.id,
                    session_id=session.id,
                    agent_release_id=release_id,
                    input_message_id=input_message_id,
                    trace_id=trace_id,
                    environment=environment,
                    origin=source,
                    input_message=input_dto.message,
                    execution_snapshot=execution_snapshot,
                    network_execution_id=context.network_execution_id if context else None,
                    network_invocation_id=context.network_invocation_id if context else None,
                    rerun_of_run_id=rerun_of_run_id,
                    storage_version=self._storage_version(),
                    started_at=datetime.now(timezone.utc),
                )
            )

            execution_payload: dict[str, Any] = {
                "run_id": str(run.id),
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id),
                "message_id": str(input_message_id) if input_message_id else None,
                "model": agent.model,
                "provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                "message_preview": input_dto.message[:200],
                "has_tools": bool(agent_tools),
                "storage_version": run.storage_version,
            }
            requested = AgentExecutionRequestedV1.create(
                agent_id=agent.id,
                session_id=session.id,
                payload=execution_payload,
            )
            await outbox.write(requested)
            await outbox.write(
                AgentExecutionStartedV1.create(
                    agent_id=agent.id,
                    session_id=session.id,
                    payload={
                        "run_id": str(run.id),
                        "trace_id": str(trace_id),
                        "model": agent.model,
                        "storage_version": run.storage_version,
                    },
                    correlation_id=requested.correlation_id,
                    causation_id=requested.event_id,
                )
            )
            return (
                run.id,
                execution_snapshot,
                agent,
                session,
                trace_id,
                primary_credential,
                fallback_credential,
                encrypted_tool_secrets,
                prepared_project_environment,
                rag_binding,
                response_format,
                json_enabled,
                agent_tools,
                tool_name_to_id,
                tools,
                history,
            )

        (
            run_id,
            execution_snapshot,
            agent,
            session,
            trace_id,
            primary_credential,
            fallback_credential,
            encrypted_tool_secrets,
            prepared_project_environment,
            rag_binding,
            response_format,
            json_enabled,
            agent_tools,
            tool_name_to_id,
            tools,
            history,
        ) = await self._transactions.run(accept_run)

        # Acceptance is durable at this point. Bind canonical identity and journal
        # ownership before decrypt, Redis hot-state work, RAG or provider I/O.
        context = current_execution.get()
        if context is not None:
            context.run_id = run_id
            context.project_id = input_dto.project_id
            context.agent_id = agent.id
            context.session_id = session.id
            context.trace_id = trace_id
            context.storage_version = self._storage_version()

        stream = current_runtime_stream.get()
        if stream is not None:
            stream.run_id = run_id
            stream.session_id = session.id
            await stream.emit("agent.run.accepted", trace_id=str(trace_id))

        await self._bind_durable_run_recorder(
            input_dto=input_dto,
            agent=agent,
            session=session,
            trace_id=trace_id,
            run_id=run_id,
            execution_snapshot=execution_snapshot,
        )

        try:
            # Decryption and all external work happen after the Acceptance COMMIT.
            api_key = self._decrypt_api_key(primary_credential)
            base_url = self._resolve_base_url(agent, primary_credential)
            fallback_data = None
            if fallback_credential is not None:
                fallback_provider = (
                    agent.fallback_provider.value
                    if hasattr(agent.fallback_provider, "value")
                    else agent.fallback_provider
                )
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

            if context is not None:
                context.prepared_fallback = fallback_data
                context.prepared_tools = {str(tool.id): tool for tool in tools}
                context.prepared_tool_secrets = tool_secrets
                context.prepared_project_environment = prepared_project_environment
                context.prepared_rag = rag_binding

            if self._execution_state_store is not None:
                await self._execution_state_store.create(
                    run_id,
                    {
                        "status": "running",
                        "phase": "prepared",
                        "project_id": str(input_dto.project_id),
                        "agent_id": str(agent.id),
                        "session_id": str(session.id),
                        "trace_id": str(trace_id),
                        "environment": normalize_runtime_environment(input_dto.execution_context),
                        "network_execution_id": str(context.network_execution_id) if context and context.network_execution_id else None,
                        "network_invocation_id": str(context.network_invocation_id) if context and context.network_invocation_id else None,
                        "attempt": context.run_attempt if context else 1,
                        "storage_version": self._storage_version(),
                    },
                    ttl_seconds=self._execution_state_ttl_seconds,
                )
                if stream is None:
                    await self._execution_state_store.append_event(
                        run_id, "agent.run.accepted", {"trace_id": str(trace_id)},
                    )

            rag_context, sources = await self._load_rag_context(
                agent,
                input_dto.message,
                self._transactions,
            )
            if context is not None and context.run_event_recorder is not None and sources:
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
            messages = self._build_messages(
                agent,
                rag_context,
                history,
                input_dto.message,
                response_format if json_enabled else None,
            )
            await self._hot_update({"phase": "llm", "rag_sources": len(sources or [])})
        except Exception as exc:
            await self._persist_prepare_failure(input_dto, exc)
            raise

        return (
            agent,
            session,
            trace_id,
            api_key,
            base_url,
            response_format,
            json_enabled,
            agent_tools,
            tool_name_to_id,
            bool(agent_tools),
            sources,
            messages,
            history,
        )

    async def _finalize(
        self,
        session,
        agent,
        input_dto,
        trace_id,
        answer,
        usage,
        response_model,
        response_provider,
        llm_latency_ms,
        sources,
        parsed_output,
        output_parse_error,
        tool_calls_recorded,
        fallback_used,
        fallback_info_result,
        json_format_latency_ms,
    ) -> AskOutput:
        context = current_execution.get()
        run_id = context.run_id if context else None
        await self._hot_terminal_pending(
            terminal_status="completed",
            result={
                "answer": answer,
                "trace_id": str(trace_id),
                "usage": usage.model_dump() if hasattr(usage, "model_dump") else None,
            },
        )

        async def finalize(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> AskOutput:
            message_id = context.output_message_id if context is not None else None
            if session:
                if message_id is None:
                    message_id = uuid4()
                    if context is not None:
                        context.output_message_id = message_id
                assistant = await self._do_save_assistant_message(
                    repositories.messages,
                    repositories.sessions,
                    outbox,
                    session,
                    answer,
                    usage,
                    agent,
                    tool_calls=tool_calls_recorded,
                    message_id=message_id,
                    data_extra={
                        "run_id": str(run_id) if run_id else None,
                        "output_mode": "final",
                    },
                )
                message_id = assistant.id

            await outbox.write(
                AgentExecutionLLMCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id,
                    payload={
                        "run_id": str(run_id) if run_id else None,
                        "trace_id": str(trace_id),
                        "latency_ms": llm_latency_ms,
                        "input_tokens": usage.input_tokens or 0,
                        "output_tokens": usage.output_tokens or 0,
                        "total_tokens": usage.total_tokens or 0,
                        "cost_usd": usage.cost_usd or 0.0,
                        "model": response_model or agent.model,
                    },
                )
            )
            for tool_call in tool_calls_recorded or []:
                await outbox.write(
                    AgentExecutionToolCompletedV1.create(
                        agent_id=agent.id,
                        session_id=session.id,
                        payload={
                            "run_id": str(run_id) if run_id else None,
                            "trace_id": str(trace_id),
                            "tool_name": tool_call.tool_name,
                            "duration_ms": tool_call.duration_ms,
                            "success": tool_call.success,
                            "error": tool_call.error,
                        },
                    )
                )

            completion_payload: dict[str, Any] = {
                "run_id": str(run_id) if run_id else None,
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id),
                "message_id": str(message_id) if message_id else None,
                "answer_length": len(answer),
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
                "total_tokens": usage.total_tokens or 0,
                "cost_usd": usage.cost_usd or 0.0,
                "model": response_model or agent.model,
                "provider": response_provider or "",
                "latency_ms": llm_latency_ms,
                "fallback_used": fallback_used,
                "sources": [item.model_dump() for item in sources] if sources else None,
                "parsed_output": parsed_output,
                "output_parse_error": output_parse_error,
                "tool_calls": [item.model_dump() for item in tool_calls_recorded] if tool_calls_recorded else [],
            }
            if fallback_info_result:
                completion_payload["fallback_info"] = fallback_info_result
                await outbox.write(
                    AgentFallbackTriggeredV1.create(
                        agent_id=agent.id,
                        session_id=session.id,
                        payload=fallback_info_result,
                    )
                )
            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id,
                    payload=completion_payload,
                )
            )
            if run_id is not None:
                run = await repositories.runs.get_by_id(run_id)
                if run is not None:
                    run.status = AgentRunStatus.COMPLETED
                    run.output_message_id = message_id
                    run.usage = usage.model_dump() if hasattr(usage, "model_dump") else None
                    run.result = completion_payload
                    run.completed_at = datetime.now(timezone.utc)
                    await repositories.runs.save(run)

            return AskOutput(
                run_id=run_id,
                answer=answer,
                session_id=session.id,
                message_id=message_id,
                usage=usage,
                sources=sources,
                tool_calls=tool_calls_recorded,
                trace_id=trace_id,
                model=response_model,
                provider=response_provider,
                fallback_used=fallback_used,
                fallback_info=fallback_info_result,
                latency_ms=llm_latency_ms or 0,
                parsed_output=parsed_output,
                output_parse_error=output_parse_error,
            )

        output = await self._transactions.run(finalize)
        if context is not None:
            context.terminal_persisted = True
        await self._hot_persisted("completed")
        return output

    async def _fail(self, trace_id, agent, session, error, input_dto) -> None:
        context = current_execution.get()
        run_id = context.run_id if context else None
        if (
            context is not None
            and context.run_event_recorder is not None
            and context.storage_version == EVENT_JOURNAL_STORAGE_VERSION
        ):
            payload = {
                "run_id": str(run_id) if run_id else None,
                "trace_id": str(trace_id) if trace_id else None,
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id),
                "error": error,
                "failure_code": "runtime_error",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            await self._hot_terminal_pending(terminal_status="failed", result=payload)
            await context.run_event_recorder.emit("run.failed", payload, durable=True)
            context.terminal_persisted = True
            await self._hot_persisted("failed")
            return

        await self._hot_terminal_pending(
            terminal_status="failed",
            result={"error": error, "trace_id": str(trace_id) if trace_id else None},
        )

        async def persist_failure(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> None:
            await outbox.write(
                AgentExecutionFailedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else (trace_id or agent.id),
                    payload={
                        "run_id": str(run_id) if run_id else None,
                        "trace_id": str(trace_id) if trace_id else None,
                        "project_id": str(input_dto.project_id),
                        "agent_id": str(agent.id),
                        "error": error,
                    },
                )
            )
            if run_id is not None:
                run = await repositories.runs.get_by_id(run_id)
                if run is not None:
                    run.status = AgentRunStatus.FAILED
                    run.failure_code = "runtime_error"
                    run.failure_detail = error[:8000]
                    run.completed_at = datetime.now(timezone.utc)
                    await repositories.runs.save(run)

        try:
            await self._transactions.run(persist_failure)
            if context is not None:
                context.terminal_persisted = True
            await self._hot_persisted("failed")
        except Exception as exc:
            logger.warning("Failed to persist Agent Run failure: %s", exc)

    async def _try_fallback(
        self,
        agent,
        messages,
        json_enabled: bool,
        primary_error: str,
    ):
        fallback_provider = (
            agent.fallback_provider.value
            if hasattr(agent.fallback_provider, "value")
            else agent.fallback_provider
        )
        context = current_execution.get()
        prepared = context.prepared_fallback if context else None
        fallback_chat_model = self._llm_factory.create_chat_model(
            provider=fallback_provider,
            model=agent.fallback_model,
            api_key=str((prepared or {}).get("api_key") or ""),
            base_url=(prepared or {}).get("base_url"),
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if json_enabled else None,
        )
        started = time.monotonic()
        fallback_result = await fallback_chat_model.ainvoke(messages)
        fallback_latency = round((time.monotonic() - started) * 1000)
        fallback_info = {
            "primary_model": agent.model,
            "primary_provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
            "primary_error": primary_error,
            "fallback_model": agent.fallback_model,
            "fallback_provider": fallback_provider,
            "fallback_credential_id": str(agent.fallback_credential_id),
        }
        if context is not None and context.run_event_recorder is not None:
            await context.run_event_recorder.emit(
                "fallback.triggered",
                fallback_info,
            )
        return fallback_result, fallback_provider, fallback_latency, fallback_info


class TransactionalAskAgentUseCase(ExplicitRuntimePersistenceMixin, AskAgentUseCase):
    """Compatibility base while orchestration is moved behind Application ports."""

    async def _load_rag_context(
        self,
        agent,
        query: str,
        transactions,
    ) -> tuple[str | None, list[SourceInfo]]:
        del agent, query, transactions
        return None, []
