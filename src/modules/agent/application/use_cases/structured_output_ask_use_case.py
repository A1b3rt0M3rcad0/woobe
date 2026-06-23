from __future__ import annotations

from modules.agent.application.mcp_tool_refresh import refresh_stale_mcp_server_tools
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.use_cases.release_runtime_resolver import ReleaseRuntimeResolver
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
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class StructuredOutputAskAgentUseCase(
    InstrumentedFallbackMixin,
    InstrumentedPrimaryExecutionMixin,
    ReleaseRuntimeResolver,
):
    """Agent execution with complete LLM and Tool telemetry."""

    async def _prepare(self, input_dto):
        prepared = await super()._prepare(input_dto)
        agent = prepared[0]
        try:
            async with AgentUnitOfWork(self._session_factory) as uow:
                tools = await uow.tools.list_by_agent(agent.id, status="active")
                refreshed_tools = await refresh_stale_mcp_server_tools(
                    tools=tools,
                    tool_repo=uow.tools,
                    executor=get_http_tool_executor(),
                )
                agent_tools, tool_name_to_id = agent_tools_to_openai_definitions_and_mapping(refreshed_tools)
        except Exception:
            return prepared

        updated = list(prepared)
        updated[7] = agent_tools
        updated[8] = tool_name_to_id
        updated[9] = bool(agent_tools)
        return tuple(updated)

    async def _finalize(
        self, session, agent, input_dto, trace_id, answer, usage,
        response_model, response_provider, llm_latency_ms, sources,
        parsed_output, output_parse_error, tool_calls_recorded,
        fallback_used, fallback_info_result, json_format_latency_ms,
    ):
        context = current_execution.get()
        if context and context.strict_json and output_parse_error:
            raise ValueError(
                f"Strict JSON output failed: {output_parse_error}"
            )
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
