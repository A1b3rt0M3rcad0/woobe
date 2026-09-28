from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.execution_instrumentation import (
    resolve_effective_output_tokens,
)
from modules.agent.infra.execution.runtime_streaming import (
    current_runtime_stream,
    runtime_streaming_enabled,
)

_skill_snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]] | None = None
_skill_runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any] | None = None


@dataclass(frozen=True, slots=True)
class PreparedFallbackModel:
    model: Any
    provider: str
    model_name: str
    pricing_snapshot: dict[str, Any] | None
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedExecution:
    """Resolved strategy-facing bindings for one Agent execution.

    The Strategy consumes this prepared view instead of repeatedly reaching back into
    Runtime plumbing. Agent Run lifecycle, persistence and terminal Run/Trace finalization
    remain owned by the outer runtime.
    """

    model: Any
    final_model: Any | None
    final_model_factory: Callable[[], Any] | None
    fallback_model_factory: Callable[[], PreparedFallbackModel] | None
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    messages: list
    tool_name_to_id: dict[str, str]
    provider: str
    model_name: str
    final_json_instruction: str | None
    pricing_snapshot: dict[str, Any] | None
    effective_output_tokens: int
    json_enabled: bool
    response_schema: dict[str, Any]
    llm_factory: Any
    api_key: str
    base_url: str | None
    clean_json_answer: Callable[..., Any]
    context_manager: ContextManager | None
    tool_definitions: list[dict]
    knowledge_retrieve: Callable[[str], Awaitable[Any]] | None
    knowledge_query: str | None
    knowledge_query_mode: str
    knowledge_history_turns: int

    @property
    def context_assembler(self) -> ContextManager | None:
        """Legacy compatibility view; internal code uses context_manager."""
        return self.context_manager


def configure_skill_runtime(
    snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]],
    runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any],
) -> None:
    """Bind concrete Skill application services from the composition root."""
    global _skill_snapshots_resolver, _skill_runtime_factory
    _skill_snapshots_resolver = snapshots_resolver
    _skill_runtime_factory = runtime_factory


def _primary_pricing_snapshot(request: ExecutionStrategyRequest) -> dict[str, Any] | None:
    settings = request.agent.settings or {}
    value = settings.get("model_pricing")
    return value if isinstance(value, dict) else None


def _fallback_pricing_snapshot(request: ExecutionStrategyRequest) -> dict[str, Any] | None:
    settings = request.agent.settings or {}
    value = settings.get("fallback_model_pricing")
    return value if isinstance(value, dict) else None


def _knowledge_query_policy(
    runtime_config: Any,
    *,
    enabled: bool,
) -> tuple[str, int]:
    if not enabled:
        return "conversation_context", 3

    raw_rag = (
        runtime_config.get("rag")
        if isinstance(runtime_config, dict)
        and isinstance(runtime_config.get("rag"), dict)
        else {}
    )
    config = RAGRuntimeConfig.model_validate(raw_rag)
    return config.query_mode, config.history_turns


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _bind_context_runtime(
    *,
    request: ExecutionStrategyRequest,
    pricing_snapshot: dict[str, Any] | None,
) -> None:
    context = current_execution.get()
    if context is None:
        return
    runtime_config = (request.agent.settings or {}).get("runtime_config")
    policy = resolve_context_policy(runtime_config)
    context.context_policy = policy.model_dump(mode="json")
    context.reserved_output_units = request.agent.max_output_tokens or 1000
    # Tool visibility belongs to one model invocation. Preparation resolves the
    # authorized inventory but does not make every Tool active in Context.
    context.active_tool_definitions = []
    context.model_capacity_units = _positive_int(
        (pricing_snapshot or {}).get("context_window")
    )
    context.context_selection_metadata = {
        "available_message_count": len(request.messages),
        "session_strategy": policy.session.strategy,
        "session_max_messages": policy.session.max_messages,
        "session_max_units": policy.session.max_units,
    }


def prepare_execution(request: ExecutionStrategyRequest) -> PreparedExecution:
    """Resolve provider/model/tool inputs without deciding the execution algorithm."""
    agent = request.agent
    provider = agent.provider.value if hasattr(agent.provider, "value") else str(agent.provider)
    runtime_config = (agent.settings or {}).get("runtime_config")
    knowledge_query_mode, knowledge_history_turns = _knowledge_query_policy(
        runtime_config,
        enabled=request.knowledge_retrieve is not None,
    )
    has_skill_config = isinstance(runtime_config, dict) and bool(runtime_config.get("skills"))
    if has_skill_config:
        if _skill_snapshots_resolver is None or _skill_runtime_factory is None:
            raise RuntimeError("Skill runtime dependencies were not configured")
        snapshots = _skill_snapshots_resolver(runtime_config, agent.project_id)
    else:
        snapshots = []

    context = current_execution.get()
    if context is not None:
        context.skill_context = None

    agent_tools = list(request.agent_tools)
    tool_name_to_id = dict(request.tool_name_to_id)
    has_tools = request.has_tools
    execute_single_tool = request.execute_single_tool

    if snapshots:
        policy = resolve_context_policy(runtime_config).skills
        if policy is None or context is None:
            raise RuntimeError("Skills require a prepared execution context and policy")
        skill_runtime = _skill_runtime_factory(snapshots, policy, set(tool_name_to_id))
        collisions = set(tool_name_to_id).intersection(skill_runtime.mapping)
        if collisions:
            raise ValueError(
                "Skill operation name collides with a bound Tool: "
                + ", ".join(sorted(collisions))
            )
        context.skill_context = skill_runtime.contributions()
        agent_tools = [*agent_tools, *skill_runtime.definitions]
        tool_name_to_id = {**tool_name_to_id, **skill_runtime.mapping}
        has_tools = True
        execute_bound_tool = execute_single_tool
        skill_execution_context = context

        async def execute_with_skills(tool_call: dict, resolved_tool_id: str) -> dict:
            name = tool_call.get("name")
            if name in skill_runtime.mapping:
                output = skill_runtime.execute(
                    name,
                    tool_call.get("args") or {},
                    tool_call_id=str(tool_call.get("id") or ""),
                )
                skill_execution_context.skill_context = skill_runtime.contributions()
                return output
            return await execute_bound_tool(tool_call, resolved_tool_id)

        execute_single_tool = execute_with_skills

    pricing_snapshot = _primary_pricing_snapshot(request)
    effective_output_tokens = resolve_effective_output_tokens(
        agent.max_output_tokens,
        pricing_snapshot,
    )
    _bind_context_runtime(
        request=request,
        pricing_snapshot=pricing_snapshot,
    )

    context = current_execution.get()
    if context is not None:
        context.execution = InstrumentedExecution(result=None)
        stream = current_runtime_stream.get()
        if stream is not None:
            setattr(stream, "execution_context", context)

    streaming_enabled = runtime_streaming_enabled()
    instruction = None
    response_schema = request.response_format.get("schema", {})
    if request.json_enabled and has_tools:
        schema_json = json.dumps(response_schema, indent=2)
        instruction = (
            "When capability calls are complete, return only valid JSON matching this "
            "schema. You may call another bound capability first when still required. "
            "Do not include markdown or explanatory text.\n"
            f"<schema>\n{schema_json}\n</schema>"
        )

    base_response_format = (
        {"type": "json_object"}
        if request.json_enabled and not has_tools
        else None
    )
    base_model = request.llm_factory.create_chat_model(
        provider=provider,
        model=agent.model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=agent.temperature or 0.2,
        max_tokens=effective_output_tokens,
        streaming=streaming_enabled,
        response_format=base_response_format,
    )
    model = base_model

    network_execution = bool(context and context.network_execution_id)
    final_model = base_model if has_tools and network_execution and not request.json_enabled else None
    final_model_factory: Callable[[], Any] | None = None
    if has_tools and request.json_enabled:

        def create_structured_recovery_model() -> Any:
            return request.llm_factory.create_chat_model(
                provider=provider,
                model=agent.model,
                api_key=request.api_key,
                base_url=request.base_url,
                temperature=agent.temperature or 0.2,
                max_tokens=effective_output_tokens,
                streaming=streaming_enabled,
                response_format={"type": "json_object"},
            )

        final_model_factory = create_structured_recovery_model

    fallback_model_factory: Callable[[], PreparedFallbackModel] | None = None
    fallback_model_name = getattr(agent, "fallback_model", None)
    fallback_credential_id = getattr(agent, "fallback_credential_id", None)
    fallback_provider_value = getattr(agent, "fallback_provider", None)
    if fallback_model_name and fallback_credential_id and fallback_provider_value:
        fallback_provider = (
            fallback_provider_value.value
            if hasattr(fallback_provider_value, "value")
            else str(fallback_provider_value)
        )
        fallback_pricing = _fallback_pricing_snapshot(request)
        fallback_output_tokens = resolve_effective_output_tokens(
            agent.max_output_tokens,
            fallback_pricing,
        )

        def create_fallback_model() -> PreparedFallbackModel:
            execution_context = current_execution.get()
            prepared_fallback = (
                execution_context.prepared_fallback
                if execution_context is not None
                else None
            )
            prepared_fallback = (
                prepared_fallback if isinstance(prepared_fallback, dict) else {}
            )
            fallback_model = request.llm_factory.create_chat_model(
                provider=fallback_provider,
                model=fallback_model_name,
                api_key=str(prepared_fallback.get("api_key") or ""),
                base_url=prepared_fallback.get("base_url"),
                temperature=agent.temperature or 0.2,
                max_tokens=fallback_output_tokens,
                streaming=streaming_enabled,
                response_format=(
                    {"type": "json_object"} if request.json_enabled else None
                ),
            )
            return PreparedFallbackModel(
                model=fallback_model,
                provider=fallback_provider,
                model_name=str(fallback_model_name),
                pricing_snapshot=fallback_pricing,
                metadata={
                    "primary_model": agent.model,
                    "primary_provider": provider,
                    "fallback_model": str(fallback_model_name),
                    "fallback_provider": fallback_provider,
                    "fallback_credential_id": str(fallback_credential_id),
                    "fallback_provider_model_id": (
                        str(getattr(agent, "fallback_provider_model_id"))
                        if getattr(agent, "fallback_provider_model_id", None)
                        else None
                    ),
                },
            )

        fallback_model_factory = create_fallback_model

    # Tool authority, grounding and Skill usage instructions are invocation-scoped.
    # Preparation owns only the stable base conversation and structured-output contract.
    execution_messages = list(request.messages)
    if instruction is not None:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            instruction,
        )

    return PreparedExecution(
        model=model,
        final_model=final_model,
        final_model_factory=final_model_factory,
        fallback_model_factory=fallback_model_factory,
        execute_single_tool=execute_single_tool,
        messages=execution_messages,
        tool_name_to_id=tool_name_to_id,
        provider=provider,
        model_name=agent.model,
        final_json_instruction=instruction,
        pricing_snapshot=pricing_snapshot,
        effective_output_tokens=effective_output_tokens,
        json_enabled=request.json_enabled,
        response_schema=response_schema,
        llm_factory=request.llm_factory,
        api_key=request.api_key,
        base_url=request.base_url,
        clean_json_answer=request.clean_json_answer,
        context_manager=request.context_manager,
        tool_definitions=agent_tools,
        knowledge_retrieve=request.knowledge_retrieve,
        knowledge_query=request.knowledge_query,
        knowledge_query_mode=knowledge_query_mode,
        knowledge_history_turns=knowledge_history_turns,
    )
