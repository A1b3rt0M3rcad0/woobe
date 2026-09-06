from __future__ import annotations

import json
from typing import Any, Callable, Coroutine
from uuid import uuid4

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.skill_bindings import frozen_enabled_skills
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.runtime_streaming import (
    current_runtime_stream,
    runtime_streaming_enabled,
)
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
    "The runtime performs a mandatory skills_search preflight before the first Model "
    "Invocation of every Run with enabled Skills. Its Tool result is already present in "
    "the current invocation history. Inspect those candidates before answering. Call "
    "skills_activate for every Skill whose described scope applies to the user's task, "
    "even when the task is simple or you could solve it directly. If matched_count is zero "
    "but installed_count is greater than zero, evaluate the catalog_fallback candidates "
    "instead of claiming that no Skill is installed. Repeat skills_search only when "
    "pagination or a refined query is actually required."
)


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


def _message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return ""


def _latest_user_query(messages: list) -> str:
    for message in reversed(messages):
        role = getattr(message, "role", None)
        message_type = getattr(message, "type", None)
        class_name = message.__class__.__name__
        if role == "user" or message_type in {"human", "user"} or class_name == "HumanMessage":
            value = _message_text(message).strip()
            if value:
                return value[:500]
    return ""


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
    snapshots = (
        frozen_enabled_skills(runtime_config, agent.project_id)
        if isinstance(runtime_config, dict) and runtime_config.get("skills")
        else []
    )
    context = current_execution.get()
    if context is not None:
        context.skill_context = None
    skill_preflight_call: dict[str, Any] | None = None
    if snapshots:
        policy = resolve_context_policy(runtime_config).skills
        if policy is None or context is None:
            raise RuntimeError("Skills require a prepared execution context and policy")
        skill_runtime = SkillRuntime(snapshots, policy, set(tool_name_to_id))
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
        skill_preflight_call = {
            "name": "skills_search",
            "args": {"query": _latest_user_query(messages)},
            "id": f"skill-preflight-{uuid4()}",
            "type": "tool_call",
        }
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
    if snapshots:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            _SKILL_RESOLUTION_INSTRUCTION,
        )
    if instruction is not None:
        execution_messages = _messages_with_leading_system_instruction(
            execution_messages,
            instruction,
        )

    execution, call_index = await run_tool_loop(
        model=model,
        final_model=final_model,
        final_model_factory=final_model_factory,
        execute_single_tool=execute_single_tool,
        messages=execution_messages,
        tool_name_to_id=tool_name_to_id,
        provider=provider,
        model_name=agent.model,
        initial_phase=(
            "capability_response_generation"
            if has_tools
            else "response_generation"
        ),
        final_json_instruction=instruction,
        initial_tool_call=skill_preflight_call,
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
