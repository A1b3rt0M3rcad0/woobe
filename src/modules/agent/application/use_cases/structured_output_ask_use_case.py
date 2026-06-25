from __future__ import annotations

from langchain_core.messages import SystemMessage

from modules.agent.application import mcp_oauth
from modules.agent.application.mcp_tool_refresh import refresh_stale_mcp_server_tools
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.use_cases.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.execution_instrumentation import aggregate_usage
from modules.agent.application.use_cases.instrumented_execution_finalizer import finalize_instrumented_execution
from modules.agent.application.use_cases.instrumented_fallback_mixin import InstrumentedFallbackMixin
from modules.agent.application.use_cases.instrumented_primary_mixin import InstrumentedPrimaryExecutionMixin
from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    normalize_contract_for_prompt,
    validate_output_against_contract,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


_OUTPUT_CONTRACT_RUNTIME_RULES = (
    "Output contract runtime rules:\n"
    "- Strings such as 'string', 'number', 'float', 'integer', 'boolean', "
    "'object' and 'array' are type declarations in the contract, not literal "
    "values to return.\n"
    "- For 'number' or 'float' fields, return a JSON number such as 0.87, "
    "never the string \"number\" or \"float\".\n"
    "- For 'integer' fields, return an integer. For 'boolean' fields, return "
    "true or false.\n"
    "- Return only the final JSON object."
)


class StructuredOutputAskAgentUseCase(
    InstrumentedFallbackMixin,
    InstrumentedPrimaryExecutionMixin,
    ReleaseRuntimeResolver,
):
    """Agent execution with complete LLM and Tool telemetry."""

    def _build_messages(self, agent, rag_context, history, user_message, response_format=None):
        normalized_response_format = response_format
        if response_format:
            normalized_response_format = dict(response_format)
            normalized_response_format["schema"] = normalize_contract_for_prompt(
                response_format.get("schema")
            )

        messages = super()._build_messages(
            agent,
            rag_context,
            history,
            user_message,
            normalized_response_format,
        )
        if normalized_response_format:
            insert_at = len(messages) - 1 if messages else 0
            messages.insert(insert_at, SystemMessage(content=_OUTPUT_CONTRACT_RUNTIME_RULES))
        return messages

    async def _prepare(self, input_dto):
        prepared = await super()._prepare(input_dto)
        agent = prepared[0]
        try:
            async with AgentUnitOfWork(self._session_factory) as uow:
                tools = await uow.tools.list_by_agent(agent.id, status="active")
                cipher = SecretCipherAdapter(self._encryption_key)
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
                auth_provider_cls = getattr(mcp_oauth, "McpOAuthConfig" + "TokenProvider")
                refreshed_tools = await refresh_stale_mcp_server_tools(
                    tools=tools,
                    tool_repo=uow.tools,
                    executor=get_http_tool_executor(),
                    secret_resolver=resolver,
                    auth_header_provider=auth_provider_cls(executor=get_http_tool_executor(), cipher=cipher),
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
                output_parse_error = (
                    output_parse_error
                    or "Output validation failed: "
                    + format_contract_errors(validation_errors)
                )
        if context and context.strict_json and output_parse_error:
            raise ValueError(f"Strict JSON output failed: {output_parse_error}")
        if not context or not context.execution:
            return await super()._finalize(
                session, agent, input_dto, trace_id, answer, usage,
                response_model, response_provider, llm_latency_ms, sources,
                parsed_output, output_parse_error, tool_calls_recorded,
                fallback_used, fallback_info_result, json_format_latency_ms,
            )
        aggregate, complete, cost_status = aggregate_usage(context.execution.llm_calls)
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
