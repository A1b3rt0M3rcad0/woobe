from __future__ import annotations

import logging
import time
from typing import Any, Protocol, cast
from uuid import uuid4

from modules.agent.application.runtime_output_validation import (
    ensure_model_result_has_public_output,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    context_assembler_key_from_runtime_config,
)
from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
    utc_now,
)
from modules.agent.application.tool_converter import MCP_PROVIDER_ROUTE_SEPARATOR
from modules.agent.domain.events import AgentExecutionFailedV1
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage
from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream

logger = logging.getLogger(__name__)


class _PrimaryExecutionSuper(Protocol):
    async def execute(self, input_dto: Any) -> Any: ...
    async def _prepare(self, input_dto: Any) -> Any: ...


class _PrimaryExecutionHost(Protocol):
    _llm_factory: Any
    _transactions: AgentRuntimeTransactionRunner
    _context_assembler: ContextAssembler | None
    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict: ...
    def _clean_json_answer(self, answer: str) -> str: ...


def _tool_runtime_output(payload: dict[str, Any]) -> dict[str, Any]:
    output = payload.get("output")
    if not isinstance(output, dict):
        return {}
    nested = output.get("output")
    return nested if isinstance(nested, dict) else output


def _copy_http_route_metadata(payload: dict[str, Any]) -> None:
    runtime_output = _tool_runtime_output(payload)
    for key in (
        "http_route_id",
        "http_operation_id",
        "http_method",
        "tool_contract_hash",
    ):
        value = runtime_output.get(key)
        if value is not None:
            payload[key] = value


class InstrumentedPrimaryExecutionMixin:
    _context_assembler: ContextAssembler | None = None

    def configure_context_assembler(self, assembler: ContextAssembler) -> None:
        self._context_assembler = assembler

    async def execute(self, input_dto: Any) -> Any:
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        existing_context = current_execution.get()
        token = None
        if existing_context is None:
            token = current_execution.set(
                new_execution_context(
                    metadata.get("server_received_at"),
                    metadata.get("client_sent_at"),
                )
            )
        elif existing_context.client_sent_at is None:
            existing_context.client_sent_at = metadata.get("client_sent_at")

        parent = cast(_PrimaryExecutionSuper, super())
        try:
            return await parent.execute(input_dto)
        except EmbeddingProviderError as exc:
            await self._persist_rag_embedding_failure(input_dto, exc)
            raise ValueError(f"RAG embedding failed: {exc}") from exc
        finally:
            if token is not None:
                current_execution.reset(token)

    async def _persist_rag_embedding_failure(
        self,
        input_dto: Any,
        exc: EmbeddingProviderError,
    ) -> None:
        host = cast(_PrimaryExecutionHost, self)
        context = current_execution.get()
        trace_id = context.trace_id if context and context.trace_id else uuid4()
        session_id = (
            context.session_id
            if context is not None and context.session_id is not None
            else getattr(input_dto, "session_id", None)
        )
        project_id = input_dto.project_id
        agent_id = input_dto.agent_id
        rag_metadata = dict(context.rag_metadata or {}) if context else {}

        if context:
            context.trace_id = trace_id
            context.project_id = project_id
            context.agent_id = agent_id
            context.session_id = session_id
            context.prepare_ended_at = context.prepare_ended_at or utc_now()

        stream = current_runtime_stream.get()
        if stream is not None and stream.trace_id is None:
            stream.bind_execution(
                trace_id=trace_id,
                session_id=session_id,
                project_id=project_id,
                agent_id=agent_id,
            )
            await stream.emit(
                "meta",
                trace_id=str(trace_id),
                session_id=str(session_id) if session_id else None,
                project_id=str(project_id),
                agent_id=str(agent_id),
            )

        payload = {
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id) if session_id else None,
            "provider": rag_metadata.get("embedding_provider"),
            "model": rag_metadata.get("embedding_model"),
            "provider_model_id": rag_metadata.get("embedding_provider_model_id"),
            "error": str(exc),
            "failure_phase": "rag_query_embedding",
            "upstream_status": exc.upstream_status,
            "upstream_error_code": exc.upstream_error_code,
            "embedding_error_category": exc.category,
            "embedding_retryable": exc.retryable,
            "execution_context": (
                context.execution_context
                if context and context.execution_context
                else getattr(input_dto, "execution_context", None)
            ),
            "agent_release_id": str(context.agent_release_id) if context and context.agent_release_id else None,
            "agent_release_version": context.agent_release_version if context else None,
            "context_assembler": (
                {
                    "name": context.context_assembler_name,
                    "version": context.context_assembler_version,
                }
                if context
                and context.context_assembler_name
                and context.context_assembler_version
                else None
            ),
            "rag_metadata": rag_metadata or None,
            "runtime_scope": "failed_rag_prepare",
        }

        async def persist_failure(_repositories, outbox) -> None:
            await outbox.write(
                AgentExecutionFailedV1.create(
                    agent_id=agent_id,
                    session_id=session_id or trace_id,
                    payload=payload,
                )
            )

        try:
            await host._transactions.run(persist_failure)
        except Exception:
            logger.exception("Failed to persist RAG embedding failure telemetry")

    async def _prepare(self, input_dto: Any) -> Any:
        context = current_execution.get()
        if context:
            context.prepare_started_at = utc_now()
        started = time.monotonic()
        parent = cast(_PrimaryExecutionSuper, super())
        try:
            prepared = await parent._prepare(input_dto)
            runtime_tool_selector = getattr(self, "_apply_runtime_tool_selection", None)
            if callable(runtime_tool_selector):
                prepared = await runtime_tool_selector(prepared)
        except Exception:
            if context:
                context.prepare_ended_at = utc_now()
                context.prepare_latency_ms = round((time.monotonic() - started) * 1000)
            raise
        if context:
            context.prepare_ended_at = utc_now()
            context.prepare_latency_ms = round((time.monotonic() - started) * 1000)
            response_format = prepared[5]
            context.strict_json = bool(
                response_format.get("enabled", False)
                and response_format.get("type") == "json"
            )
            agent, session, trace_id = prepared[0], prepared[1], prepared[2]
            settings = getattr(agent, "settings", None)
            settings = settings if isinstance(settings, dict) else {}
            assembler_key = context_assembler_key_from_runtime_config(
                settings.get("runtime_config")
            )
            context.context_assembler_name = assembler_key.name
            context.context_assembler_version = assembler_key.version
            context.project_id = getattr(agent, "project_id", None)
            context.agent_id = getattr(agent, "id", None)
            context.session_id = getattr(session, "id", None) if session else None
            context.trace_id = trace_id

        stream = current_runtime_stream.get()
        if stream is not None:
            agent, session, trace_id = prepared[0], prepared[1], prepared[2]
            sources = prepared[10]
            if stream.trace_id is None:
                stream.bind_execution(
                    trace_id=trace_id,
                    session_id=session.id if session else None,
                    project_id=input_dto.project_id,
                    agent_id=agent.id,
                )
                await stream.emit(
                    "meta",
                    trace_id=str(trace_id),
                    session_id=str(session.id) if session else None,
                    project_id=str(input_dto.project_id),
                    agent_id=str(agent.id),
                )
            if sources:
                await stream.emit(
                    "sources",
                    sources=[source.model_dump() for source in sources],
                )
        return prepared

    async def _execute_llm(
        self,
        agent: Any,
        api_key: str,
        base_url: str | None,
        response_format: dict,
        json_enabled: bool,
        has_tools: bool,
        agent_tools: list[dict],
        tool_name_to_id: dict[str, str],
        messages: list,
    ) -> tuple[Any, list, bool, Any]:
        host = cast(_PrimaryExecutionHost, self)
        try:
            execution = await run_instrumented_execution(
                llm_factory=host._llm_factory,
                context_assembler=host._context_assembler,
                execute_single_tool=host._execute_single_tool,
                clean_json_answer=host._clean_json_answer,
                agent=agent,
                api_key=api_key,
                base_url=base_url,
                response_format=response_format,
                json_enabled=json_enabled,
                has_tools=has_tools,
                agent_tools=agent_tools,
                tool_name_to_id=tool_name_to_id,
                messages=messages,
            )
        except InstrumentedExecutionError as exc:
            context = current_execution.get()
            if context:
                context.execution = InstrumentedExecution(
                    result=None,
                    tool_calls=exc.tool_calls,
                    llm_calls=exc.llm_calls,
                    timeline=exc.timeline,
                    tool_wall_latency_ms=exc.tool_wall_latency_ms,
                    tool_call_duration_sum_ms=exc.tool_call_duration_sum_ms,
                    failure_context=exc.failure_context,
                )
            raise

        context = current_execution.get()
        if context and context.tool_metadata:
            snapshots = context.tool_snapshots or {}
            for item in execution.timeline:
                if item.get("kind") != "tool":
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                tool_name = payload.get("tool_name")
                route = tool_name_to_id.get(str(tool_name)) if tool_name else None
                tool_id = (
                    route.split(MCP_PROVIDER_ROUTE_SEPARATOR, 1)[0]
                    if route
                    else None
                )
                snapshot = snapshots.get(tool_id) if tool_id else None
                payload["tool_id"] = tool_id
                payload["tool_runtime_source"] = context.tool_metadata.get("source")
                _copy_http_route_metadata(payload)
                if snapshot and snapshot.get("snapshot_hash"):
                    payload["tool_snapshot_hash"] = snapshot["snapshot_hash"]

        if context and context.rag_metadata:
            occurred_at = context.prepare_ended_at or utc_now()
            execution.timeline.append(
                {
                    "kind": "rag",
                    "occurred_at": occurred_at,
                    "payload": {
                        "occurred_at": occurred_at,
                        "started_at": context.prepare_started_at,
                        "ended_at": context.prepare_ended_at or occurred_at,
                        **context.rag_metadata,
                    },
                }
            )
        if context:
            context.execution = execution
        ensure_model_result_has_public_output(execution.result)
        usage, _, _ = aggregate_usage(execution.llm_calls)
        execution.result.usage_metadata = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        repaired = any(
            call.get("phase") == "json_repair"
            for call in execution.llm_calls
        )
        repair_latency = execution.llm_calls[-1].get("latency_ms") if repaired else None
        return execution.result, execution.tool_calls, bool(execution.tool_calls), repair_latency
