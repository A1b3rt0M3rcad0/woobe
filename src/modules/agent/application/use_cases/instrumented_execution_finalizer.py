from __future__ import annotations

import time
from typing import Any

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput, UsageInfo
from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
)
from modules.agent.domain.entities import Agent, Session
from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionToolCompletedV1,
    AgentFallbackTriggeredV1,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


async def finalize_instrumented_execution(
    owner,
    *,
    session: Session | None,
    agent: Agent,
    input_dto: AskInput,
    trace_id: Any,
    answer: str,
    usage: UsageInfo,
    response_model: str | None,
    response_provider: str | None,
    sources: list,
    parsed_output: dict | None,
    output_parse_error: str | None,
    execution: InstrumentedExecution,
    fallback_used: bool,
    fallback_info: dict[str, Any] | None,
    started_at: float,
    prepare_latency_ms: int,
    usage_complete: bool,
    cost_status: str,
) -> AskOutput:
    persistence_started = time.monotonic()
    async with AgentUnitOfWork(owner._session_factory) as uow:
        outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        message_id = None
        if session:
            assistant_message = await owner._do_save_assistant_message(
                uow.messages,
                uow.sessions,
                outbox,
                session,
                answer,
                usage,
                agent,
                tool_calls=execution.tool_calls,
            )
            message_id = assistant_message.id

        for item in sorted(
            execution.timeline,
            key=lambda value: str(value.get("occurred_at") or ""),
        ):
            payload = {"trace_id": str(trace_id), **dict(item["payload"])}
            event = (
                AgentExecutionLLMCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=payload,
                )
                if item["kind"] == "llm"
                else AgentExecutionToolCompletedV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload=payload,
                )
            )
            await outbox.write(event)

        if fallback_info:
            await outbox.write(
                AgentFallbackTriggeredV1.create(
                    agent_id=agent.id,
                    session_id=session.id if session else None,
                    payload={"trace_id": str(trace_id), **fallback_info},
                )
            )

        persistence_latency_ms = round(
            (time.monotonic() - persistence_started) * 1000
        )
        total_latency_ms = round((time.monotonic() - started_at) * 1000)
        llm_runtime_latency_ms = sum(
            int(call.get("latency_ms") or 0) for call in execution.llm_calls
        )
        orchestration_latency_ms = max(
            total_latency_ms
            - prepare_latency_ms
            - persistence_latency_ms
            - llm_runtime_latency_ms
            - execution.tool_wall_latency_ms,
            0,
        )
        tool_http_latency_ms = sum(
            int(item["payload"].get("http_latency_ms") or 0)
            for item in execution.timeline
            if item.get("kind") == "tool"
        )
        completion_payload = {
            "trace_id": str(trace_id),
            "project_id": str(input_dto.project_id),
            "agent_id": str(agent.id),
            "session_id": str(session.id) if session else None,
            "message_id": str(message_id) if message_id else None,
            "answer_length": len(answer),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
            "cost_status": cost_status,
            "usage_complete": usage_complete,
            "model": response_model or agent.model,
            "provider": response_provider or "",
            "latency_ms": total_latency_ms,
            "total_latency_ms": total_latency_ms,
            "prepare_latency_ms": prepare_latency_ms,
            "persistence_latency_ms": persistence_latency_ms,
            "orchestration_latency_ms": orchestration_latency_ms,
            "llm_runtime_latency_ms": llm_runtime_latency_ms,
            "tool_wall_latency_ms": execution.tool_wall_latency_ms,
            "tool_call_duration_sum_ms": execution.tool_call_duration_sum_ms,
            "tool_http_latency_ms": tool_http_latency_ms,
            "fallback_used": fallback_used,
            "sources": [source.model_dump() for source in sources] if sources else [],
            "parsed_output": parsed_output,
            "output_parse_error": output_parse_error,
            "tool_calls": [tool.model_dump() for tool in execution.tool_calls],
            "llm_calls": execution.llm_calls,
        }
        if fallback_info:
            completion_payload["fallback_info"] = fallback_info
        await outbox.write(
            AgentExecutionCompletedV1.create(
                agent_id=agent.id,
                session_id=session.id if session else None,
                payload=completion_payload,
            )
        )

    return AskOutput(
        answer=answer,
        session_id=session.id if session else None,
        message_id=message_id,
        usage=usage,
        sources=sources,
        tool_calls=execution.tool_calls,
        trace_id=trace_id,
        model=response_model,
        provider=response_provider,
        fallback_used=fallback_used,
        fallback_info=fallback_info,
        latency_ms=total_latency_ms,
        parsed_output=parsed_output,
        output_parse_error=output_parse_error,
    )
