from __future__ import annotations

import time
from typing import Any, Protocol, cast

from modules.agent.application.tool_converter import MCP_PROVIDER_ROUTE_SEPARATOR
from modules.agent.application.use_cases.execution_context import (
    current_execution,
    new_execution_context,
    utc_now,
)
from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
    InstrumentedExecutionError,
    aggregate_usage,
)
from modules.agent.application.use_cases.instrumented_execution_runner import (
    run_instrumented_execution,
)
from modules.agent.application.use_cases.runtime_streaming import (
    current_runtime_stream,
)


class _PrimaryExecutionSuper(Protocol):
    async def execute(self, input_dto: Any) -> Any: ...
    async def _prepare(self, input_dto: Any) -> Any: ...


class _PrimaryExecutionHost(Protocol):
    _llm_factory: Any
    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict: ...
    def _clean_json_answer(self, answer: str) -> str: ...


class InstrumentedPrimaryExecutionMixin:
    async def execute(self, input_dto: Any) -> Any:
        metadata = input_dto.metadata if isinstance(input_dto.metadata, dict) else {}
        token = current_execution.set(
            new_execution_context(
                metadata.get("server_received_at"),
                metadata.get("client_sent_at"),
            )
        )
        parent = cast(_PrimaryExecutionSuper, super())
        try:
            return await parent.execute(input_dto)
        finally:
            current_execution.reset(token)

    async def _prepare(self, input_dto: Any) -> Any:
        context = current_execution.get()
        if context:
            context.prepare_started_at = utc_now()
        started = time.monotonic()
        parent = cast(_PrimaryExecutionSuper, super())
        prepared = await parent._prepare(input_dto)
        if context:
            context.prepare_ended_at = utc_now()
            context.prepare_latency_ms = round((time.monotonic() - started) * 1000)
            response_format = prepared[5]
            context.strict_json = bool(response_format.get("strict", False))
            agent, session, trace_id = prepared[0], prepared[1], prepared[2]
            context.project_id = getattr(agent, "project_id", None)
            context.agent_id = getattr(agent, "id", None)
            context.session_id = getattr(session, "id", None) if session else None
            context.trace_id = trace_id

        stream = current_runtime_stream.get()
        if stream is not None:
            agent, session, trace_id = prepared[0], prepared[1], prepared[2]
            sources = prepared[10]
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
                tool_id = route.split(MCP_PROVIDER_ROUTE_SEPARATOR, 1)[0] if route else None
                snapshot = snapshots.get(tool_id) if tool_id else None
                payload["tool_id"] = tool_id
                payload["tool_runtime_source"] = context.tool_metadata.get("source")
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
        usage, _, _ = aggregate_usage(execution.llm_calls)
        execution.result.usage_metadata = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        repaired = any(call.get("phase") == "json_repair" for call in execution.llm_calls)
        repair_latency = execution.llm_calls[-1].get("latency_ms") if repaired else None
        return execution.result, execution.tool_calls, bool(execution.tool_calls), repair_latency
