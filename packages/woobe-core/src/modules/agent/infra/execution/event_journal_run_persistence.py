from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import uuid6

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.agent_run_metrics import build_agent_run_metrics
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


def _id_text(value: Any) -> str | None:
    return str(value) if value else None


def _provider_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _recorder():
    context = current_execution.get()
    recorder = context.run_event_recorder if context is not None else None
    if recorder is None:
        raise RuntimeError("Durable Agent Run journal recorder is not bound")
    return context, recorder


class EventJournalAgentRunPersistence:
    storage_version = EVENT_JOURNAL_STORAGE_VERSION

    async def complete(self, owner: Any, **kw: Any) -> AskOutput:
        context, recorder = _recorder()
        execution = kw["execution"]
        agent = kw["agent"]
        session = kw["session"]
        usage = kw["usage"]
        completed_at = datetime.now(timezone.utc).isoformat()
        metrics = build_agent_run_metrics(
            context=context,
            execution=execution,
            binding=agent,
            fallback_used=kw["fallback_used"],
            finalization_work_ms=0,
            prepare_latency_ms=kw.get("prepare_latency_ms"),
            usage=usage,
            usage_complete=kw.get("usage_complete"),
            cost_status=kw.get("cost_status"),
            completed_at=completed_at,
        )
        canonical_usage = metrics.usage
        message_id = uuid6.uuid7() if session is not None else None
        sources = kw.get("sources") or []
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(kw["trace_id"]),
            "project_id": str(kw["input_dto"].project_id),
            "agent_id": str(agent.id),
            "session_id": str(session.id) if session else None,
            "message_id": str(message_id) if message_id else None,
            "answer": kw["answer"],
            "usage": canonical_usage.model_dump(),
            "input_tokens": canonical_usage.input_tokens,
            "output_tokens": canonical_usage.output_tokens,
            "total_tokens": canonical_usage.total_tokens,
            "cost_usd": canonical_usage.cost_usd,
            "provider": kw.get("response_provider") or _provider_value(agent.provider),
            "model": kw.get("response_model") or agent.model,
            "provider_model_id": _id_text(getattr(agent, "provider_model_id", None)),
            "provider_credential_id": _id_text(
                getattr(agent, "provider_credential_id", None)
            ),
            "fallback_provider_model_id": _id_text(
                getattr(agent, "fallback_provider_model_id", None)
            ),
            "fallback_credential_id": _id_text(
                getattr(agent, "fallback_credential_id", None)
            ),
            "fallback_used": bool(kw["fallback_used"]),
            "fallback_info": kw.get("fallback_info"),
            "sources": [
                source.model_dump() if hasattr(source, "model_dump") else source
                for source in sources
            ],
            "tool_calls": [
                call.model_dump() if hasattr(call, "model_dump") else call
                for call in execution.tool_calls
            ],
            # Kept as a compact compatibility summary. Canonical invocation facts are
            # already separate model.invocation.* journal events.
            "llm_calls": list(execution.llm_calls),
            "parsed_output": kw.get("parsed_output"),
            "output_parse_error": kw.get("output_parse_error"),
            "diagnostics": metrics.diagnostics,
            "latency_ms": metrics.total_latency_ms,
            "started_at": metrics.started_at,
            "completed_at": metrics.completed_at,
            "timeline_complete": True,
        }
        await owner._hot_terminal_pending(terminal_status="completed", result=payload)
        await recorder.emit("run.completed", payload, durable=True)
        context.terminal_persisted = True
        await owner._hot_persisted("completed")
        output = AskOutput(
            run_id=context.run_id,
            answer=kw["answer"],
            session_id=session.id if session else None,
            message_id=message_id,
            usage=canonical_usage,
            sources=sources,
            tool_calls=execution.tool_calls,
            trace_id=kw["trace_id"],
            model=kw.get("response_model"),
            provider=kw.get("response_provider"),
            provider_model_id=getattr(agent, "provider_model_id", None),
            provider_credential_id=getattr(agent, "provider_credential_id", None),
            fallback_provider_model_id=getattr(
                agent, "fallback_provider_model_id", None
            ),
            fallback_credential_id=getattr(agent, "fallback_credential_id", None),
            fallback_used=bool(kw["fallback_used"]),
            fallback_info=kw.get("fallback_info"),
            latency_ms=metrics.total_latency_ms,
            parsed_output=kw.get("parsed_output"),
            output_parse_error=kw.get("output_parse_error"),
            diagnostics=metrics.diagnostics,
        )
        return output

    async def fail(self, owner: Any, **kw: Any) -> None:
        context, recorder = _recorder()
        execution = kw["execution"]
        aggregate, usage_complete, cost_status = aggregate_usage(execution.llm_calls)
        metrics = build_agent_run_metrics(
            context=context,
            execution=execution,
            binding=kw["agent"],
            fallback_used=False,
            finalization_work_ms=0,
            prepare_latency_ms=kw.get("prepare_latency_ms"),
            usage=aggregate,
            usage_complete=usage_complete,
            cost_status=cost_status,
        )
        failure_context = execution.failure_context or {}
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(kw["trace_id"]),
            "project_id": str(kw["input_dto"].project_id),
            "agent_id": str(kw["agent"].id),
            "session_id": str(kw["session"].id) if kw.get("session") else None,
            "error": str(kw["error"]),
            "failure_code": str(failure_context.get("phase") or "runtime_error"),
            "usage": aggregate.model_dump(),
            "tool_calls": [
                call.model_dump() if hasattr(call, "model_dump") else call
                for call in execution.tool_calls
            ],
            "llm_calls": list(execution.llm_calls),
            "diagnostics": metrics.diagnostics,
            "latency_ms": metrics.total_latency_ms,
            "completed_at": metrics.completed_at,
            "timeline_complete": False,
        }
        await owner._hot_terminal_pending(terminal_status="failed", result=payload)
        await recorder.emit("run.failed", payload, durable=True)
        context.terminal_persisted = True
        await owner._hot_persisted("failed")

    async def prepare_failure(
        self,
        owner: Any,
        *,
        input_dto: Any,
        error: Exception,
    ) -> bool:
        context, recorder = _recorder()
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(context.trace_id) if context.trace_id else None,
            "project_id": str(input_dto.project_id),
            "agent_id": str(context.agent_id or input_dto.agent_id),
            "session_id": str(context.session_id) if context.session_id else None,
            "error": str(error),
            "failure_code": "prepare_failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await owner._hot_terminal_pending(terminal_status="failed", result=payload)
        await recorder.emit("run.failed", payload, durable=True)
        context.terminal_persisted = True
        await owner._hot_persisted("failed")
        return True
