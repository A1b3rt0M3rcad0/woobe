from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput, SourceInfo
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.outbox import OutboxEventWriter
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
from modules.agent.infra.execution.runtime_preparation import (
    build_execution_snapshot,
    prepare_rag_binding,
    prepare_tool_state,
)
from shared.contracts.execution_state import ExecutionStateStore
from shared.infra.crypto import decrypt_secret
from shared.runtime_environment import normalize_runtime_environment

logger = logging.getLogger(__name__)


class ExplicitRuntimePersistenceMixin:
    """Exactly one durable Acceptance and one durable terminal write per Agent Run."""

    _execution_state_store: ExecutionStateStore | None = None
    _execution_state_ttl_seconds = 3600
    _execution_terminal_ttl_seconds = 900

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
            "phase": "finalize",
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
            )
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
            history = await self._load_history(repositories.messages, session) if session else []
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

            run = await repositories.runs.create(
                AgentRun(
                    project_id=input_dto.project_id,
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    agent_release_id=release_id,
                    input_message_id=input_message_id,
                    trace_id=trace_id,
                    environment=environment,
                    origin=source,
                    input_message=input_dto.message,
                    execution_snapshot=build_execution_snapshot(
                        agent=agent,
                        tools=tools,
                        rag_binding=rag_binding,
                        release_id=release_id,
                        release_version=release_version,
                        tool_to_snapshot=tool_to_release_snapshot,
                    ),
                    network_execution_id=context.network_execution_id if context else None,
                    network_invocation_id=context.network_invocation_id if context else None,
                    rerun_of_run_id=rerun_of_run_id,
                    started_at=datetime.now(timezone.utc),
                )
            )

            execution_payload: dict[str, Any] = {
                "run_id": str(run.id),
                "trace_id": str(trace_id),
                "project_id": str(input_dto.project_id),
                "agent_id": str(agent.id),
                "session_id": str(session.id) if session else None,
                "message_id": str(input_message_id) if input_message_id else None,
                "model": agent.model,
                "provider": agent.provider.value if hasattr(agent.provider, "value") else agent.provider,
                "message_preview": input_dto.message[:200],
                "has_tools": bool(agent_tools),
            }
            requested = AgentExecutionRequestedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload=execution_payload,
            )
            await outbox.write(requested)
            await outbox.write(
                AgentExecutionStartedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload={
                        "run_id": str(run.id),
                        "trace_id": str(trace_id),
                        "model": agent.model,
                    },
                    correlation_id=requested.correlation_id,
                    causation_id=requested.event_id,
                )
            )
            return (
                run.id,
                agent,
                session,
                trace_id,
                primary_credential,
                fallback_credential,
                encrypted_tool_secrets,
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
            agent,
            session,
            trace_id,
            primary_credential,
            fallback_credential,
            encrypted_tool_secrets,
            rag_binding,
            response_format,
            json_enabled,
            agent_tools,
            tool_name_to_id,
            tools,
            history,
        ) = await self._transactions.run(accept_run)

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

        context = current_execution.get()
        if context is not None:
            context.run_id = run_id
            context.project_id = input_dto.project_id
            context.agent_id = agent.id
            context.session_id = session.id if session else None
            context.trace_id = trace_id
            context.prepared_fallback = fallback_data
            context.prepared_tools = {str(tool.id): tool for tool in tools}
            context.prepared_tool_secrets = tool_secrets
            context.prepared_rag = rag_binding

        if self._execution_state_store is not None:
            await self._execution_state_store.create(
                run_id,
                {
                    "status": "running",
                    "phase": "prepared",
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(agent.id),
                    "session_id": str(session.id) if session else None,
                    "trace_id": str(trace_id),
                    "environment": normalize_runtime_environment(input_dto.execution_context),
                    "network_execution_id": str(context.network_execution_id) if context and context.network_execution_id else None,
                    "network_invocation_id": str(context.network_invocation_id) if context and context.network_invocation_id else None,
                    "attempt": 1,
                },
                ttl_seconds=self._execution_state_ttl_seconds,
            )
            await self._execution_state_store.append_event(
                run_id,
                "agent.run.accepted",
                {"trace_id": str(trace_id)},
            )

        rag_context, sources = await self._load_rag_context(
            agent,
            input_dto.message,
            self._transactions,
        )
        messages = self._build_messages(
            agent,
            rag_context,
            history,
            input_dto.message,
            response_format if json_enabled else None,
        )
        await self._hot_update({"phase": "llm", "rag_sources": len(sources or [])})
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
            message_id = None
            if session:
                assistant = await self._do_save_assistant_message(
                    repositories.messages,
                    repositories.sessions,
                    outbox,
                    session,
                    answer,
                    usage,
                    agent,
                    tool_calls=tool_calls_recorded,
                )
                message_id = assistant.id

            await outbox.write(
                AgentExecutionLLMCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
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
                        session_id=session.id if session else None,
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
                "session_id": str(session.id) if session else None,
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
                        session_id=session.id if session else None,
                        payload=fallback_info_result,
                    )
                )
            await outbox.write(
                AgentExecutionCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
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
                session_id=session.id if session else None,
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
