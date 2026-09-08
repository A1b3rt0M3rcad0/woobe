from __future__ import annotations

import json
from typing import Any, Callable, Coroutine

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.runtime_streaming import (
    current_runtime_stream,
    runtime_streaming_enabled,
)
from modules.agent.infra.execution.skill_routing_model import SkillRoutingModelAdapter
from modules.agent.infra.execution.structured_json_repair import repair_json_if_needed
from modules.agent.infra.execution.tool_execution_loop import run_tool_loop

_BOUND_CAPABILITIES_INSTRUCTION = (
    "The capabilities bound to this Model Invocation are the complete and authoritative "
    "set currently available to this Agent. Do not search for, list, discover, or invent "
    "additional capabilities. Do not infer capability availability from previous Session "
    "messages or prior executions. Use only the capabilities currently bound by the runtime "
    "when they are needed; otherwise answer directly."
)

_SKILL_RESOLUTION_INSTRUCTION = (
    "The installed Skill catalog is routing metadata for the Skills enabled on this Agent "
    "Run. This invocation is exclusively for Skill applicability resolution for the CURRENT "
    "USER REQUEST. Do not answer the user's request in this invocation. Prefer calling the "
    "bound skills_resolve operation exactly once. Choose activate when the request matches a "
    "visible Skill's when_to_use scope, none when no installed Skill applies, or search only "
    "when catalog_complete is false or the visible routing metadata is insufficient. Match "
    "semantic intent rather than literal keywords: a request can express a covered operation "
    "through symbols or examples, such as an expression using '+' matching a Skill whose "
    "when_to_use covers addition or arithmetic. If the model/provider does not emit a Tool "
    "call, return ONLY one JSON object with the same decision: "
    "{\"action\":\"activate\",\"skill_version_id\":\"<uuid>\"}, "
    "{\"action\":\"none\"}, or {\"action\":\"search\",\"query\":\"<query>\",\"offset\":0}. "
    "Do not include markdown or explanatory text. Determine applicability from the current "
    "request, not from previous Session messages, prior Runs, or earlier Skill usage. Do not "
    "activate a Skill merely because it is installed, was used earlier, or is mentioned in "
    "conversation history. Do not search merely to confirm a Skill already listed in a "
    "complete catalog. When a Skill is activated, its procedural instructions become "
    "runtime-only context for this Agent Run and must be followed subject to higher-priority "
    "Agent and system policies."
)

_skill_snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]] | None = None
_skill_runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any] | None = None


def configure_skill_runtime(
    snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]],
    runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any],
) -> None:
    """Bind concrete Skill application services from the composition root."""
    global _skill_snapshots_resolver, _skill_runtime_factory
    _skill_snapshots_resolver = snapshots_resolver
    _skill_runtime_factory = runtime_factory


def _primary_pricing_snapshot(agent: Agent) -> dict[str, Any] | None:
    settings = agent.settings or {}
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
    agent: Agent,
    agent_tools: list[dict],
    messages: list,
    pricing_snapshot: dict[str, Any] | None,
) -> None:
    context = current_execution.get()
    if context is None:
        return
    runtime_config = (agent.settings or {}).get("runtime_config")
    policy = resolve_context_policy(runtime_config)
    context.context_policy = policy.model_dump(mode="json")
    context.reserved_output_units = agent.max_output_tokens or 1000
    context.active_tool_definitions = list(agent_tools)
    context.model_capacity_units = _positive_int(
        (pricing_snapshot or {}).get("context_window")
    )
    context.context_selection_metadata = {
        "available_message_count": len(messages),
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
            merged_content = [
                *content,
                {"type": "text", "text": instruction},
            ]
        else:
            merged_content = instruction
        result[0] = first.model_copy(update={"content": merged_content})
        return result
    return [SystemMessage(content=instruction), *result]


def _messages_with_bound_capability_authority(
    messages: list, *, has_tools: bool, has_skills: bool = False
) -> list:
    if not has_tools:
        return list(messages)
    return _messages_with_leading_system_instruction(
        messages,
        (
            _BOUND_CAPABILITIES_INSTRUCTION.replace(
                "Do not search for, list, discover, or invent additional capabilities.",
                "Skill discovery may find installed procedures, but never grants additional Tool permissions.",
            )
            if has_skills
            else _BOUND_CAPABILITIES_INSTRUCTION
        ),
    )


def _skill_routing_messages(messages: list) -> list:
    """Keep Skill applicability classification focused on the current request.

    The Context Manager will inject the immutable installed-Skill catalog into this
    minimal message set. Agent persona, Session history, Knowledge, and unrelated
    conversational material are intentionally excluded from the routing invocation.
    """
    for message in reversed(messages):
        if message.__class__.__name__ == "HumanMessage":
            return [SystemMessage(content=_SKILL_RESOLUTION_INSTRUCTION), message]
    raise RuntimeError("Skill routing requires a current user message")


async def run_instrumented_execution(
    *,
    llm_factory: Any,
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]],
    clean_json_answer,
    agent: Agent,
    api_key: str,
    base_url: str | None,
    response_format: dict,
    json_enabled: bool,
    has_tools: bool,
    agent_tools: list[dict],
    tool_name_to_id: dict[str, str],
    messages: list,
    context_assembler: ContextAssembler | None = None,
) -> InstrumentedExecution:
    provider = (
        agent.provider.value
        if hasattr(agent.provider, "value")
        else str(agent.provider)
    )
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
    skill_runtime = None
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
    pricing_snapshot = _primary_pricing_snapshot(agent)
    _bind_context_runtime(
        agent=agent,
        agent_tools=agent_tools,
        messages=messages,
        pricing_snapshot=pricing_snapshot,
    )
    context = current_execution.get()
    if context is not None:
        # Keep an execution accumulator reachable while provider/tool work is still
        # in flight. Cancellation is a terminal result too, so observability cannot
        # depend on run_tool_loop returning successfully before evidence becomes visible.
        context.execution = InstrumentedExecution(result=None)
        stream = current_runtime_stream.get()
        if stream is not None:
            setattr(stream, "execution_context", context)

    streaming_enabled = runtime_streaming_enabled()
    instruction = None
    if json_enabled and has_tools:
        schema_json = json.dumps(response_format.get("schema", {}), indent=2)
        instruction = (
            "When capability calls are complete, return only valid JSON matching this "
            "schema. You may call another bound capability first when still required. "
            "Do not include markdown or explanatory text.\n"
            f"<schema>\n{schema_json}\n</schema>"
        )

    base_response_format = (
        {"type": "json_object"}
        if json_enabled and not has_tools
        else None
    )
    base_model = llm_factory.create_chat_model(
        provider=provider,
        model=agent.model,
        api_key=api_key,
        base_url=base_url,
        temperature=agent.temperature or 0.2,
        max_tokens=agent.max_output_tokens or 1000,
        streaming=streaming_enabled,
        response_format=base_response_format,
    )
    model = base_model.bind_tools(agent_tools, tool_choice="auto") if has_tools else base_model
    routing_model = None
    if skill_runtime is not None:
        routing_model = SkillRoutingModelAdapter(
            base_model.bind_tools(
                [skill_runtime.routing_definition],
                tool_choice="auto",
            ),
            clean_json_answer=clean_json_answer,
        )

    network_execution = bool(context and context.network_execution_id)
    # Terminal recovery is exceptional. Delay constructing its structured model until
    # the capability loop actually reaches a terminal/circuit-breaker path.
    final_model = base_model if has_tools and network_execution and not json_enabled else None
    final_model_factory: Callable[[], Any] | None = None
    if has_tools and json_enabled:

        def create_structured_recovery_model() -> Any:
            return llm_factory.create_chat_model(
                provider=provider,
                model=agent.model,
                api_key=api_key,
                base_url=base_url,
                temperature=agent.temperature or 0.2,
                max_tokens=agent.max_output_tokens or 1000,
                streaming=streaming_enabled,
                response_format={"type": "json_object"},
            )

        final_model_factory = create_structured_recovery_model

    execution_messages = _messages_with_bound_capability_authority(
        messages,
        has_tools=has_tools,
        has_skills=bool(snapshots),
    )
    if instruction is not None:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            instruction,
        )
    routing_messages = (
        _skill_routing_messages(messages)
        if skill_runtime is not None
        else None
    )

    followup_model_selector: Callable[[], Any] | None = None
    completion_guard: Callable[[], bool] | None = None
    if skill_runtime is not None:
        if routing_model is None:
            raise RuntimeError("Skill routing model was not configured")

        def select_skill_followup_model() -> Any:
            return model if skill_runtime.routing_resolved else routing_model

        followup_model_selector = select_skill_followup_model
        completion_guard = lambda: skill_runtime.routing_resolved

    execution, call_index = await run_tool_loop(
        model=model,
        initial_model=routing_model,
        initial_messages=routing_messages,
        followup_model_selector=followup_model_selector,
        completion_guard=completion_guard,
        completion_guard_error=(
            "Skill applicability routing did not resolve before Agent response generation"
        ),
        final_model=final_model,
        final_model_factory=final_model_factory,
        execute_single_tool=execute_single_tool,
        messages=execution_messages,
        tool_name_to_id=tool_name_to_id,
        provider=provider,
        model_name=agent.model,
        initial_phase=(
            "skill_resolution"
            if skill_runtime is not None
            else "capability_response_generation"
            if has_tools
            else "response_generation"
        ),
        final_json_instruction=instruction,
        pricing_snapshot=pricing_snapshot,
        context_assembler=context_assembler,
    )
    if not json_enabled:
        return execution
    return await repair_json_if_needed(
        execution=execution,
        call_index=call_index,
        llm_factory=llm_factory,
        provider=provider,
        model_name=agent.model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=agent.max_output_tokens or 1000,
        schema=response_format.get("schema", {}),
        clean_json_answer=clean_json_answer,
        pricing_snapshot=pricing_snapshot,
        context_assembler=context_assembler,
    )
