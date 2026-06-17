from __future__ import annotations

from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.execution_instrumentation import aggregate_usage
from modules.agent.application.use_cases.instrumented_execution_finalizer import (
    finalize_instrumented_execution,
)
from modules.agent.application.use_cases.instrumented_fallback_mixin import (
    InstrumentedFallbackMixin,
)
from modules.agent.application.use_cases.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)


class StructuredOutputAskAgentUseCase(
    InstrumentedFallbackMixin,
    InstrumentedPrimaryExecutionMixin,
    AskAgentUseCase,
):
    """Agent execution with complete LLM and Tool telemetry."""

    async def _finalize(
        self, session, agent, input_dto, trace_id, answer, usage,
        response_model, response_provider, llm_latency_ms, sources,
        parsed_output, output_parse_error, tool_calls_recorded,
        fallback_used, fallback_info_result, json_format_latency_ms,
    ):
        context = current_execution.get()
        if not context or not context.execution:
            return await super()._finalize(
                session, agent, input_dto, trace_id, answer, usage,
                response_model, response_provider, llm_latency_ms, sources,
                parsed_output, output_parse_error, tool_calls_recorded,
                fallback_used, fallback_info_result, json_format_latency_ms,
            )
        aggregate, complete, cost_status = aggregate_usage(
            context.execution.llm_calls
        )
        return await finalize_instrumented_execution(
            self,
            session=session,
            agent=agent,
            input_dto=input_dto,
            trace_id=trace_id,
            answer=answer,
            usage=aggregate,
            response_model=response_model,
            response_provider=response_provider,
            sources=sources or [],
            parsed_output=parsed_output,
            output_parse_error=output_parse_error,
            execution=context.execution,
            fallback_used=fallback_used,
            fallback_info=fallback_info_result,
            started_at=context.started_at,
            prepare_latency_ms=context.prepare_latency_ms,
            usage_complete=complete,
            cost_status=cost_status,
        )
