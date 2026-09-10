from __future__ import annotations

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    validate_output_against_contract,
)
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class JournalAwareAgentRuntime(FrozenSnapshotStructuredOutputRuntime):
    """Switch terminal durability without contaminating the legacy execution pipeline."""

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
    ):
        context = current_execution.get()
        persistence = getattr(self, "_run_persistence", None)
        if (
            context is None
            or context.storage_version != EVENT_JOURNAL_STORAGE_VERSION
            or getattr(context, "defer_persistence", False)
            or context.execution is None
            or persistence is None
        ):
            return await super()._finalize(
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
            )

        context.persisted_sources = list(sources or [])
        response_format = self._get_response_format(agent)
        if (
            response_format.get("enabled", False)
            and response_format.get("type") == "json"
            and parsed_output is not None
        ):
            validation_errors = validate_output_against_contract(
                parsed_output,
                response_format.get("schema"),
            )
            if validation_errors:
                output_parse_error = output_parse_error or (
                    "Output validation failed: " + format_contract_errors(validation_errors)
                )
        if context.strict_json and output_parse_error:
            raise ValueError(f"Strict JSON output failed: {output_parse_error}")

        aggregate, complete, cost_status = aggregate_usage(context.execution.llm_calls)
        return await persistence.complete(
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

    async def _fail(self, trace_id, agent, session, error, input_dto) -> None:
        context = current_execution.get()
        persistence = getattr(self, "_run_persistence", None)
        if (
            context is not None
            and context.storage_version == EVENT_JOURNAL_STORAGE_VERSION
            and not getattr(context, "defer_persistence", False)
            and context.execution is not None
            and persistence is not None
        ):
            await persistence.fail(
                self,
                session=session,
                agent=agent,
                input_dto=input_dto,
                trace_id=trace_id,
                error=error,
                execution=context.execution,
                started_at=context.started_at,
                prepare_latency_ms=context.prepare_latency_ms,
            )
            return
        await super()._fail(trace_id, agent, session, error, input_dto)
