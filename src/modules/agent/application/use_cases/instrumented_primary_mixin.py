from __future__ import annotations

import time

from modules.agent.application.use_cases.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
    InstrumentedExecutionError,
    aggregate_usage,
)
from modules.agent.application.use_cases.instrumented_execution_runner import (
    run_instrumented_execution,
)


class InstrumentedPrimaryExecutionMixin:
    async def execute(self, input_dto):
        token = current_execution.set(new_execution_context())
        try:
            return await super().execute(input_dto)
        finally:
            current_execution.reset(token)

    async def _prepare(self, input_dto):
        started = time.monotonic()
        prepared = await super()._prepare(input_dto)
        context = current_execution.get()
        if context:
            context.prepare_latency_ms = round(
                (time.monotonic() - started) * 1000
            )
        return prepared

    async def _execute_llm(
        self,
        agent,
        api_key,
        base_url,
        response_format,
        json_enabled,
        has_tools,
        agent_tools,
        tool_name_to_id,
        messages,
    ):
        try:
            execution = await run_instrumented_execution(
                llm_factory=self._llm_factory,
                execute_single_tool=self._execute_single_tool,
                clean_json_answer=self._clean_json_answer,
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
        if context:
            context.execution = execution
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
        repair_latency = (
            execution.llm_calls[-1].get("latency_ms")
            if repaired
            else None
        )
        return (
            execution.result,
            execution.tool_calls,
            bool(execution.tool_calls),
            repair_latency,
        )
