from __future__ import annotations

import time
from uuid import uuid4

from modules.agent.application.runtime_output_validation import (
    ensure_model_result_has_public_output,
)
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.execution_instrumentation import (
    aggregate_usage,
    utc_iso,
)
from modules.agent.infra.execution.runtime_streaming import emit_runtime_event
from shared.contracts.llm_cost import calculate_llm_cost
from shared.contracts.llm_usage import normalize_llm_usage


def _fallback_pricing_snapshot(agent) -> dict | None:
    settings = getattr(agent, "settings", None) or {}
    value = settings.get("fallback_model_pricing")
    return value if isinstance(value, dict) else None


def _cost_context(pricing_snapshot: dict | None) -> dict:
    if not pricing_snapshot:
        return {
            "provider_model_id": None,
            "provider_credential_id": None,
            "pricing_id": None,
            "pricing_snapshot": None,
        }
    return {
        "provider_model_id": pricing_snapshot.get("provider_model_id"),
        "provider_credential_id": pricing_snapshot.get("provider_credential_id"),
        "pricing_id": pricing_snapshot.get("pricing_id"),
        "pricing_snapshot": pricing_snapshot,
    }


class InstrumentedFallbackMixin:
    async def _try_fallback(self, agent, messages, json_enabled, primary_error):
        primary_provider = (
            agent.provider.value
            if hasattr(agent.provider, "value")
            else str(agent.provider)
        )
        fallback_provider = (
            agent.fallback_provider.value
            if hasattr(agent.fallback_provider, "value")
            else str(agent.fallback_provider)
        )
        await emit_runtime_event(
            "fallback",
            primary_provider=primary_provider,
            primary_model=agent.model,
            fallback_provider=fallback_provider,
            fallback_model=agent.fallback_model,
            error=str(primary_error),
        )

        started_at = utc_iso()
        started = time.monotonic()
        parent_try_fallback = getattr(super(), "_try_fallback")
        response = await parent_try_fallback(
            agent, messages, json_enabled, primary_error
        )
        result, provider, _latency, _info = response
        ended_at = utc_iso()
        raw = normalize_llm_usage(result)
        pricing_snapshot = _fallback_pricing_snapshot(agent)
        cost = calculate_llm_cost(
            input_tokens=raw.get("input_tokens"),
            output_tokens=raw.get("output_tokens"),
            pricing_snapshot=pricing_snapshot,
        )
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
            "cost_usd": cost["cost_usd"],
            "cost_status": cost["cost_status"],
            "cost_reason": cost["cost_reason"],
            "usage_complete": all(
                raw.get(field) is not None
                for field in ("input_tokens", "output_tokens", "total_tokens")
            ),
            "provider": provider,
            "model": agent.fallback_model,
            **_cost_context(pricing_snapshot),
        }
        execution.result = result
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": ended_at, "payload": call}
        )
        if context:
            context.execution = execution
        ensure_model_result_has_public_output(result)
        usage, _, _ = aggregate_usage(execution.llm_calls)
        result.usage_metadata = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        return response
