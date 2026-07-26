from __future__ import annotations

from uuid import UUID

from langchain_core.messages import SystemMessage

from modules.agent.application import mcp_oauth
from modules.agent.application.mcp_tool_refresh import refresh_stale_mcp_server_tools
from modules.agent.application.runtime_tool_inventory import RUNTIME_TOOL_INVENTORY_NAME
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping
from modules.agent.application.tool_release_snapshots import tool_with_permission_overrides
from modules.agent.application.use_cases.session_continuity_runtime_resolver import (
    SessionContinuityReleaseRuntimeResolver,
)
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.application.use_cases.execution_instrumentation import aggregate_usage
from modules.agent.application.use_cases.instrumented_execution_finalizer import finalize_instrumented_execution
from modules.agent.application.use_cases.instrumented_failed_finalizer import finalize_failed_instrumented_execution
from modules.agent.application.use_cases.instrumented_fallback_mixin import InstrumentedFallbackMixin
from modules.agent.application.use_cases.instrumented_primary_mixin import InstrumentedPrimaryExecutionMixin
from modules.agent.application.use_cases.structured_output_contract import (
    format_contract_errors,
    normalize_contract_for_prompt,
    validate_output_against_contract,
)
from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.events import AgentExecutionFailedV1, AgentMessageCreatedV1
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.time import utc_now


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

_RUNTIME_TOOL_INVENTORY_RUNTIME_RULES = (
    "Runtime tool inventory rule: if the user asks what tools, MCP providers, "
    "integrations, external access, or runtime capabilities are available, call "
    f"{RUNTIME_TOOL_INVENTORY_NAME} before answering."
)

_TOOL_GROUNDING_RUNTIME_RULES = (
    "Tool grounding rules:\n"
    "- Never invent identifiers, owners, repository names, URLs, resource IDs, "
    "tenant IDs, slugs or keys required by a Tool.\n"
    "- If a qualified identifier is missing, use a real discovery or search Tool "
    "when one is available.\n"
    "- If no discovery Tool is available, ask the user for the missing identifier.\n"
    "- Do not try guessed candidates or fabricated alternatives after a Tool rejects "
    "an identifier or reports that a resource was not found."
)


def _id_text(value) -> str | None:
    return str(value) if value else None


def _provider_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


class StructuredOutputAskAgentUseCase(
    InstrumentedFallbackMixin,
    InstrumentedPrimaryExecutionMixin,
    SessionContinuityReleaseRuntimeResolver,
):
    """Agent execution with complete LLM and Tool telemetry."""

    def _resolve_base_url_for_provider(self, provider_val, credential, settings):
        """Resolve OpenAI-compatible custom gateways without legacy model metadata.

        ProviderModel is now the canonical source for the model slug. The custom
        provider resolver should only require a base_url; the actual model is
        passed to the LLM factory through agent.model or agent.fallback_model.
        This keeps compatibility with older credentials while allowing reusable
        ProviderModel bindings to drive playground, staging, production, and
        fallback executions.
        """
        return super()._resolve_base_url_for_provider(provider_val, credential, settings)

    async def _prepare(self, input_dto):
        prepared = await super()._prepare(input_dto)
        if not isinstance(prepared, tuple) or len(prepared) < 13:
            return prepared

        agent = prepared[0]
        session = prepared[1]
        messages = list(prepared[11])
        context = current_execution.get()
        if context is not None:
            context.session_id = session.id if session is not None else None

        response_format = prepared[5]
        json_enabled = prepared[6]
        has_tools = prepared[9]
        if json_enabled:
            contract = normalize_contract_for_prompt(response_format)
            if contract:
                messages.insert(0, SystemMessage(content=f"{_OUTPUT_CONTRACT_RUNTIME_RULES}\n\n{contract}"))

        if has_tools:
            messages.insert(0, SystemMessage(content=_TOOL_GROUNDING_RUNTIME_RULES))
            messages.insert(0, SystemMessage(content=_RUNTIME_TOOL_INVENTORY_RUNTIME_RULES))

        mutable = list(prepared)
        mutable[11] = messages
        return tuple(mutable)

    async def _execute_llm(self, *args, **kwargs):
        result, tool_calls, tool_was_called, json_format_latency_ms = await super()._execute_llm(*args, **kwargs)
        context = current_execution.get()
        if context is not None:
            aggregate_usage(context)
        return result, tool_calls, tool_was_called, json_format_latency_ms

    async def _finalize(self, session, agent, input_dto, trace_id, answer, usage, response_model, response_provider, llm_latency_ms, sources, parsed_output, output_parse_error, tool_calls_recorded, fallback_used, fallback_info_result, json_format_latency_ms):
        output = await super()._finalize(
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
        context = current_execution.get()
        if context is not None:
            await finalize_instrumented_execution(
                context=context,
                output=output,
                input_dto=input_dto,
            )
        return output

    async def _fail(self, trace_id, agent, session, error, input_dto):
        await super()._fail(trace_id, agent, session, error, input_dto)
        context = current_execution.get()
        if context is not None:
            await finalize_failed_instrumented_execution(
                context=context,
                error=error,
                input_dto=input_dto,
            )

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        if self._tool_executor_factory is None:
            return await super()._execute_single_tool(tool_call, tool_id)
        return await self._tool_executor_factory(UUID(tool_id), tool_call.get("args", {}) or {})

    async def _load_rag_context(self, agent, message, uow):
        return await super()._load_rag_context(agent, message, uow)

    async def _read_agent_tools_for_runtime(self, agent_id):
        if self._session_factory is None:
            return []
        async with AgentUnitOfWork(self._session_factory) as uow:
            tools = await uow.tools.list_by_agent(agent_id, status="active")
            refreshed = []
            for tool in tools:
                config = tool.config or {}
                if config.get("provider") == "mcp":
                    try:
                        tool = await refresh_stale_mcp_server_tools(
                            uow,
                            tool,
                            cipher=SecretCipherAdapter(self._encryption_key),
                            secret_resolver=ToolSecretResolverAdapter(uow.tool_secrets, SecretCipherAdapter(self._encryption_key)),
                            executor=get_http_tool_executor(),
                            oauth=mcp_oauth,
                        )
                    except Exception:
                        pass
                refreshed.append(tool)
            return refreshed
