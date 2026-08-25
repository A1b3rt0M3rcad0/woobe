from __future__ import annotations

import json
from typing import Any, Callable, Coroutine

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.runtime_streaming import runtime_streaming_enabled
from modules.agent.infra.execution.structured_json_repair import repair_json_if_needed
from modules.agent.infra.execution.tool_execution_loop import run_tool_loop


def _primary_pricing_snapshot(agent: Agent) -> dict[str, Any] | None:
    settings = agent.settings or {}
    value = settings.get("model_pricing")
    return value if isinstance(value, dict) else None


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
) -> InstrumentedExecution:
    provider = (
        agent.provider.value
        if hasattr(agent.provider, "value")
        else str(agent.provider)
    )
    pricing_snapshot = _primary_pricing_snapshot(agent)
    streaming_enabled = runtime_streaming_enabled()
    base_response_format = (
        {"type": "json_object"}
        if json_enabled and not has_tools
        else None
    )
    model = llm_factory.create_chat_model(
        provider=provider,
        model=agent.model,
        api_key=api_key,
        base_url=base_url,
        temperature=agent.temperature or 0.2,
        max_tokens=agent.max_output_tokens or 1000,
        streaming=streaming_enabled,
        response_format=base_response_format,
    )
    final_model = None
    if has_tools:
        final_model = llm_factory.create_chat_model(
            provider=provider,
            model=agent.model,
            api_key=api_key,
            base_url=base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            streaming=streaming_enabled,
            response_format={"type": "json_object"} if json_enabled else None,
        )
        model = model.bind_tools(agent_tools, tool_choice="auto")

    instruction = None
    if json_enabled and has_tools:
        schema_json = json.dumps(response_format.get("schema", {}), indent=2)
        instruction = (
            "After all required tool calls are complete, return only valid JSON "
            "matching this schema. You may call another tool first when still "
            "required. Do not include markdown or explanatory text.\n"
            f"<schema>\n{schema_json}\n</schema>"
        )

    execution, call_index = await run_tool_loop(
        model=model,
        final_model=final_model,
        execute_single_tool=execute_single_tool,
        messages=messages,
        tool_name_to_id=tool_name_to_id,
        provider=provider,
        model_name=agent.model,
        initial_phase="tool_planning" if has_tools else "response_generation",
        final_json_instruction=instruction,
        pricing_snapshot=pricing_snapshot,
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
    )
