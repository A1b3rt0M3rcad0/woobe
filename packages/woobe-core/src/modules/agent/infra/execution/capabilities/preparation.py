from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.context_assembler import ContextAssembler
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

_BOUND_CAPABILITIES_INSTRUCTION = (
    "The capabilities bound to this Model Invocation are the complete and authoritative "
    "set currently available to this Agent. Do not search for, list, discover, or invent "
    "additional capabilities. Do not infer capability availability from previous Session "
    "messages or prior executions. Use only the capabilities currently bound by the runtime "
    "when they are needed; otherwise answer directly."
)

_SKILL_USAGE_INSTRUCTION = (
    "The installed Skill catalog contains metadata only; Skill instructions and "
    "resources are not loaded. Decide whether a Skill helps fulfill the current "
    "user request as part of your normal response. If no Skill applies, answer "
    "directly without any Skill operation or routing decision. When a visible "
    "Skill applies, call skills_activate with its exact skill_version_id before "
    "following that procedure. Do not search to confirm a Skill already visible. "
    "Use skills_search only when it is available and relevant metadata is omitted "
    "from an incomplete catalog. A search result is metadata, not an activation. "
    "Match semantic intent, including equivalent expressions and symbols. Use "
    "Session context to understand the current request, but never activate a Skill "
    "solely because it was installed or used in an earlier Run. Read resources "
    "only when needed. Loaded procedures remain subject to Agent and system "
    "policies and are retained only for the current Agent Run."
)

_skill_snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]] | None = None
_skill_runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any] | None = None


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
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    messages: list
    tool_name_to_id: dict[str, str]
    provider: str
    model_name: str
    initial_phase: str
    final_json_instruction: str | None
    pricing_snapshot: dict[str, Any] | None
    effective_output_tokens: int
    json_enabled: bool
    response_schema: dict[str, Any]
    llm_factory: Any
    api_key: str
    base_url: str | None
    clean_json_answer: Callable[..., Any]
    context_assembler: ContextAssembler | None
    tool_definitions: list[dict]
    knowledge_retrieve: Callable[[str], Awaitable[Any]] | None
    knowledge_query: str | None


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
    agent_tools: list[dict],
    pricing_snapshot: dict[str, Any] | None,
) -> None:
    context = current_execution.get()
    if context is None:
        return
    runtime_config = (request.agent.settings or {}).get("runtime_config")
    policy = resolve_context_policy(runtime_config)
    context.context_policy = policy.model_dump(mode="json")
    context.reserved_output_units = request.agent.max_output_tokens or 1000
    context.active_tool_definitions = list(agent_tools)
    context.model_capacity_units = _positive_int(
        (pricing_snapshot or {}).get("context_window")
    )
    context.context_selection_metadata = {
        "available_message_count": len(request.messages),
        "session_strategy": policy.session.strategy,
        "session_max_messages": policy.session.max_messages,
        "session_max_units": policy.session.max_units,
    }


def _messages_with_leading_system_instruction(messages: list, instruction: str) -> list:
    result = list(messages)
    if result and isinstance(result[0], SystemMessage):
        first = result[0]
        content = first.content
        if isinstance(content, str):
            merged_content = f"{content}\n\n{instruction}"
        elif isinstance(content, list):
            merged_content = [*content, {"type": "text", "text": instruction}]
        else:
            merged_content = instruction
        result[0] = first.model_copy(update={"content": merged_content})
        return result
    return [SystemMessage(content=instruction), *result]


def _messages_with_bound_capability_authority(
    messages: list,
    *,
    has_tools: bool,
    has_skills: bool = False,
) -> list:
    if not has_tools:
        return list(messages)
    instruction = _BOUND_CAPABILITIES_INSTRUCTION
    if has_skills:
        instruction = instruction.replace(
            "Do not search for, list, discover, or invent additional capabilities.",
            "Installed Skill discovery may be available when explicitly bound by the "
            "runtime, but it never grants additional Tool permissions.",
        )
    return _messages_with_leading_system_instruction(messages, instruction)


def prepare_execution(request: ExecutionStrategyRequest) -> PreparedExecution:
    """Resolve provider/model/tool inputs without deciding the execution algorithm."""
    agent = request.agent
    provider = agent.provider.value if hasattr(agent.provider, "value") else str(agent.provider)
    runtime_config = (agent.settings or {}).get("runtime_config")
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
        agent_tools=agent_tools,
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
    model = base_model.bind_tools(agent_tools, tool_choice="auto") if has_tools else base_model

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

    execution_messages = _messages_with_bound_capability_authority(
        request.messages,
        has_tools=has_tools,
        has_skills=bool(snapshots),
    )
    if snapshots:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            _SKILL_USAGE_INSTRUCTION,
        )
    if instruction is not None:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            instruction,
        )

    return PreparedExecution(
        model=model,
        final_model=final_model,
        final_model_factory=final_model_factory,
        execute_single_tool=execute_single_tool,
        messages=execution_messages,
        tool_name_to_id=tool_name_to_id,
        provider=provider,
        model_name=agent.model,
        initial_phase=(
            "capability_response_generation" if has_tools else "response_generation"
        ),
        final_json_instruction=instruction,
        pricing_snapshot=pricing_snapshot,
        effective_output_tokens=effective_output_tokens,
        json_enabled=request.json_enabled,
        response_schema=response_schema,
        llm_factory=request.llm_factory,
        api_key=request.api_key,
        base_url=request.base_url,
        clean_json_answer=request.clean_json_answer,
        context_assembler=request.context_assembler,
        tool_definitions=agent_tools,
        knowledge_retrieve=request.knowledge_retrieve,
        knowledge_query=request.knowledge_query,
    )
