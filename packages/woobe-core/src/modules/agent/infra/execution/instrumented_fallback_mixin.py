from __future__ import annotations

from modules.agent.application.runtime_output_validation import (
    ensure_model_result_has_public_output,
)
from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.durable_execution_instrumentation import (
    aggregate_usage,
    resolve_effective_output_tokens,
)
from modules.agent.infra.execution.strategy_runtime.context_manager import (
    materialize_context_contributions,
)
from modules.agent.infra.execution.runtime_streaming import (
    emit_runtime_event,
    runtime_streaming_enabled,
)


def _fallback_pricing_snapshot(agent) -> dict | None:
    settings = getattr(agent, "settings", None) or {}
    value = settings.get("fallback_model_pricing")
    return value if isinstance(value, dict) else None


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

        context = current_execution.get()
        prepared = context.prepared_fallback if context else None
        execution = (
            context.execution
            if context and context.execution
            else InstrumentedExecution(result=None)
        )
        call_index = len(execution.llm_calls) + 1
        pricing_snapshot = _fallback_pricing_snapshot(agent)
        effective_output_tokens = resolve_effective_output_tokens(
            agent.max_output_tokens,
            pricing_snapshot,
        )
        fallback_chat_model = self._llm_factory.create_chat_model(
            provider=fallback_provider,
            model=agent.fallback_model,
            api_key=str((prepared or {}).get("api_key") or ""),
            base_url=(prepared or {}).get("base_url"),
            temperature=agent.temperature or 0.2,
            max_tokens=effective_output_tokens,
            streaming=runtime_streaming_enabled(),
            response_format={"type": "json_object"} if json_enabled else None,
        )
        fallback_messages = list(messages)
        if context is not None and context.strategy_context_contributions:
            fallback_messages = materialize_context_contributions(
                fallback_messages,
                tuple(context.strategy_context_contributions.values()),
            )
        try:
            fallback_context = ContextAssemblyCapability(
                assembler=getattr(self, "_context_assembler", None),
                provider=fallback_provider,
                model_name=agent.fallback_model,
                pricing_snapshot=pricing_snapshot,
            ).assemble(
                messages=fallback_messages,
                phase="final_response_generation",
                tool_selection_mode="none",
                call_index=call_index,
            )
            fallback_capability = ModelInvocationCapability(
                model=fallback_chat_model,
                provider=fallback_provider,
                model_name=agent.fallback_model,
                pricing_snapshot=pricing_snapshot,
            )
            result, call = await fallback_capability.invoke(
                messages=list(fallback_context.messages),
                # Fallback is a terminal response generation attempt. Reusing the
                # public final phase keeps standalone and Network streaming semantics
                # identical while the fallback event preserves provider provenance.
                phase="final_response_generation",
                call_index=call_index,
                invocation_id=fallback_context.invocation_id,
                context_snapshot=fallback_context.snapshot,
                context_prepared=True,
            )
        except InstrumentedExecutionError as exc:
            existing_call_ids = {
                call.get("call_id")
                for call in execution.llm_calls
                if call.get("call_id")
            }
            merged_calls = [
                *execution.llm_calls,
                *[
                    call
                    for call in exc.llm_calls
                    if not call.get("call_id") or call.get("call_id") not in existing_call_ids
                ],
            ]
            existing_timeline_call_ids = {
                item.get("payload", {}).get("call_id")
                for item in execution.timeline
                if isinstance(item.get("payload"), dict)
            }
            merged_timeline = [
                *execution.timeline,
                *[
                    item
                    for item in exc.timeline
                    if not isinstance(item.get("payload"), dict)
                    or not item["payload"].get("call_id")
                    or item["payload"].get("call_id") not in existing_timeline_call_ids
                ],
            ]
            merged = InstrumentedExecution(
                result=None,
                tool_calls=list(execution.tool_calls),
                llm_calls=merged_calls,
                knowledge_calls=list(execution.knowledge_calls),
                sources=list(execution.sources),
                timeline=merged_timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=exc.failure_context,
            )
            if context:
                context.execution = merged
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=merged_calls,
                tool_calls=list(execution.tool_calls),
                knowledge_calls=list(execution.knowledge_calls),
                sources=list(execution.sources),
                timeline=merged_timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=exc.failure_context,
            ) from exc

        execution.result = result
        execution.llm_calls.append(call)
        execution.timeline.append(
            {
                "kind": "llm",
                "occurred_at": call["occurred_at"],
                "payload": call,
            }
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
        fallback_info = {
            "primary_model": agent.model,
            "primary_provider": primary_provider,
            "primary_error": str(primary_error),
            "fallback_model": agent.fallback_model,
            "fallback_provider": fallback_provider,
            "fallback_credential_id": (
                str(agent.fallback_credential_id)
                if getattr(agent, "fallback_credential_id", None)
                else None
            ),
            "fallback_provider_model_id": (
                str(agent.fallback_provider_model_id)
                if getattr(agent, "fallback_provider_model_id", None)
                else None
            ),
        }
        return (
            result,
            fallback_provider,
            int(call.get("latency_ms") or 0),
            fallback_info,
        )
