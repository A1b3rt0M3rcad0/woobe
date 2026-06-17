from __future__ import annotations

import time
from uuid import uuid4

from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
    aggregate_usage,
    utc_iso,
)
from shared.infra.llm_usage import normalize_llm_usage


class InstrumentedFallbackMixin:
    async def _try_fallback(self, agent, messages, json_enabled, primary_error):
        started_at = utc_iso()
        started = time.monotonic()
        response = await super()._try_fallback(
            agent, messages, json_enabled, primary_error
        )
        result, provider, _latency, _info = response
        ended_at = utc_iso()
        raw = normalize_llm_usage(result)
        context = current_execution.get()
        execution = (
            context.execution
            if context and context.execution
            else InstrumentedExecution(result=None)
        )
        call = {
            "call_id": str(uuid4()),
            "call_index": len(execution.llm_calls) + 1,
            "phase": "fallback_response",
            "status": "success",
            "error": None,
            "started_at": started_at,
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "input_tokens": raw.get("input_tokens"),
            "output_tokens": raw.get("output_tokens"),
            "total_tokens": raw.get("total_tokens"),
            "cost_usd": raw.get("cost_usd"),
            "cost_status": (
                "known" if raw.get("cost_usd") is not None else "unknown"
            ),
            "usage_complete": all(
                raw.get(field) is not None
                for field in ("input_tokens", "output_tokens", "total_tokens")
            ),
            "provider": provider,
            "model": agent.fallback_model,
        }
        execution.result = result
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": ended_at, "payload": call}
        )
        if context:
            context.execution = execution
        usage, _, _ = aggregate_usage(execution.llm_calls)
        result.usage_metadata = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        return response
