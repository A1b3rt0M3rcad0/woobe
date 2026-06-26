from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine

from langchain_core.messages import SystemMessage

from modules.agent.application.use_cases.ask_use_case import _has_tool_calls
from modules.agent.application.use_cases.execution_instrumentation import (
    InstrumentedExecution,
    InstrumentedExecutionError,
    execute_tool_call,
    invoke_llm,
)

_NO_MORE_TOOLS_SENTINEL = "__NO_MORE_TOOLS__"
_TOOL_DECISION_INSTRUCTION = (
    "Tool decision phase only. Decide whether another tool call is required to satisfy "
    "the latest user request. If a tool is required, call the tool. If no more tools are "
    f"required, reply exactly {_NO_MORE_TOOLS_SENTINEL}. Do not answer the user. Do not "
    "summarize. Do not generate final user-facing content."
)
_FINAL_RESPONSE_INSTRUCTION = (
    "Generate one single final user-facing answer for the latest user request. "
    "Fulfill every part of that request completely and in the same order the user asked. "
    "If the user asked for a story and then a calculation, include the full story first "
    "and then include the calculation result. Use the verified tool results above exactly "
    "where relevant. Do not call tools. Do not mention internal planning or execution phases."
)


def _message_content(message: Any) -> str:
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


def _is_user_message(message: Any) -> bool:
    role = getattr(message, "role", None)
    message_type = getattr(message, "type", None)
    class_name = message.__class__.__name__
    return role == "user" or message_type in {"human", "user"} or class_name == "HumanMessage"


def _latest_user_request(messages: list) -> str:
    for message in reversed(messages):
        if _is_user_message(message):
            content = _message_content(message).strip()
            if content:
                return content
    return ""


def _tool_decision_messages(messages: list) -> list:
    return [*messages, SystemMessage(content=_TOOL_DECISION_INSTRUCTION)]


def _build_final_response_instruction(
    *,
    messages: list,
    final_json_instruction: str | None,
) -> str:
    latest_request = _latest_user_request(messages)
    request_block = (
        f"\n\nLatest user request:\n<user_request>\n{latest_request}\n</user_request>"
        if latest_request
        else ""
    )
    json_block = (
        "\n\nStructured output requirement:\n"
        f"{final_json_instruction}"
        if final_json_instruction
        else ""
    )
    return (
        f"{_FINAL_RESPONSE_INSTRUCTION}"
        f"{request_block}"
        "\n\nThe conversation above includes any verified tool results. Use those tool results "
        "as facts. Do not omit non-tool parts of the latest user request. Do not summarize "
        "content the user explicitly asked to be long, complete, or detailed."
        f"{json_block}"
    )


def _final_response_messages(messages: list, final_json_instruction: str | None) -> list:
    return [
        *messages,
        SystemMessage(
            content=_build_final_response_instruction(
                messages=messages,
                final_json_instruction=final_json_instruction,
            )
        ),
    ]


async def run_tool_loop(
    *,
    model: Any,
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]],
    messages: list,
    tool_name_to_id: dict[str, str],
    provider: str,
    model_name: str,
    initial_phase: str,
    final_json_instruction: str | None,
    final_model: Any | None = None,
) -> tuple[InstrumentedExecution, int]:
    execution = InstrumentedExecution(result=None)
    call_index = 1
    result, call = await invoke_llm(
        model=model,
        messages=_tool_decision_messages(messages) if final_model is not None else messages,
        phase=initial_phase,
        call_index=call_index,
        provider=provider,
        model_name=model_name,
    )
    execution.llm_calls.append(call)
    execution.timeline.append(
        {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
    )

    round_index = 0
    instruction_added = False
    while _has_tool_calls(result) and round_index < 5:
        round_index += 1
        messages.append(result)
        tool_calls = list(getattr(result, "tool_calls", None) or [])
        started = time.monotonic()
        results = await asyncio.gather(
            *[
                execute_tool_call(
                    execute=execute_single_tool,
                    tool_call=tool_call,
                    resolved_tool_id=tool_name_to_id.get(
                        tool_call["name"], tool_call["name"]
                    ),
                )
                for tool_call in tool_calls
            ]
        )
        execution.tool_wall_latency_ms += round(
            (time.monotonic() - started) * 1000
        )
        for info, message, payload in results:
            execution.tool_calls.append(info)
            execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            messages.append(message)

        if final_model is None and final_json_instruction and not instruction_added:
            messages.append(SystemMessage(content=final_json_instruction))
            instruction_added = True

        call_index += 1
        try:
            result, call = await invoke_llm(
                model=model,
                messages=(
                    _tool_decision_messages(messages)
                    if final_model is not None
                    else messages
                ),
                phase=f"tool_followup_{round_index}",
                call_index=call_index,
                provider=provider,
                model_name=model_name,
            )
        except InstrumentedExecutionError as exc:
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=execution.llm_calls + exc.llm_calls,
                tool_calls=execution.tool_calls,
                timeline=execution.timeline + exc.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            ) from exc
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    if _has_tool_calls(result):
        raise InstrumentedExecutionError(
            "Tool call round limit exceeded",
            llm_calls=execution.llm_calls,
            tool_calls=execution.tool_calls,
            timeline=execution.timeline,
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
        )

    if final_model is not None:
        call_index += 1
        try:
            result, call = await invoke_llm(
                model=final_model,
                messages=_final_response_messages(messages, final_json_instruction),
                phase="final_response_generation",
                call_index=call_index,
                provider=provider,
                model_name=model_name,
            )
        except InstrumentedExecutionError as exc:
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=execution.llm_calls + exc.llm_calls,
                tool_calls=execution.tool_calls,
                timeline=execution.timeline + exc.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            ) from exc
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    execution.result = result
    return execution, call_index
