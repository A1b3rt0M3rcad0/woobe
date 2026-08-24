from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Coroutine

from langchain_core.messages import AIMessage, SystemMessage

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.infra.execution.ask_use_case import _has_tool_calls
from modules.agent.infra.execution.execution_instrumentation import (
    execute_tool_call,
    invoke_llm,
)

MAX_TOOL_ROUNDS = 5
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2

_TOOL_DECISION_INSTRUCTION = (
    "Tool decision phase only. Decide whether another tool call is required to satisfy "
    "the latest user request. If another tool call is required, call the tool. If no "
    "more tool calls are required, do not call any tool. Do not answer the user. Do not "
    "summarize. Do not generate final user-facing content. Any text content from this "
    "phase is ignored and will not be shown to the user."
)
_FINAL_RESPONSE_INSTRUCTION = (
    "Generate one single final user-facing answer for the latest user request. "
    "Fulfill every part of that request completely and in the same order the user asked. "
    "Use successful Tool results exactly where relevant. Explain failed Tool-dependent "
    "parts accurately and ask for missing information when required. Do not invent "
    "identifiers or fabricate successful results. Do not call Tools. Do not mention "
    "internal planning or execution phases."
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


def _is_tool_message(message: Any) -> bool:
    role = getattr(message, "role", None)
    message_type = getattr(message, "type", None)
    class_name = message.__class__.__name__
    return role == "tool" or message_type == "tool" or class_name == "ToolMessage"


def _sanitize_base_messages(messages: list) -> list:
    """Remove raw historical Tool payloads before a new LLM execution."""
    sanitized: list = []
    for message in messages:
        if _is_tool_message(message):
            continue
        if getattr(message, "tool_calls", None):
            sanitized.append(AIMessage(content=_message_content(message)))
        else:
            sanitized.append(message)
    return sanitized


def _latest_user_request(messages: list) -> str:
    for message in reversed(messages):
        if _is_user_message(message):
            content = _message_content(message).strip()
            if content:
                return content
    return ""


def _json_preview(value: Any, *, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _extract_tool_result(output: Any) -> Any:
    if not isinstance(output, dict):
        return output
    if "result" in output:
        return output["result"]
    nested = output.get("output")
    if isinstance(nested, dict):
        if "result" in nested:
            return nested["result"]
        body = nested.get("body")
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        if body is not None:
            return body
    return output


def _tool_results_summary(tool_calls: list[Any]) -> str:
    if not tool_calls:
        return ""
    lines: list[str] = []
    for index, call in enumerate(tool_calls, start=1):
        tool_name = getattr(call, "tool_name", None) or "tool"
        tool_input = getattr(call, "input", None)
        output = getattr(call, "output", None)
        success = getattr(call, "success", None)
        error_code = getattr(call, "error_code", None)
        error = getattr(call, "error", None)
        result = _extract_tool_result(output)
        status = "success" if success is not False else "failed"
        input_preview = _json_preview(tool_input) if tool_input is not None else "{}"
        if success is False:
            code = f" [{error_code}]" if error_code else ""
            result_preview = f"error{code}: {error or 'Tool execution failed'}"
        else:
            result_preview = _json_preview(result)
        lines.append(f"{index}. {tool_name}({input_preview}) -> {status}: {result_preview}")
    return "\n".join(lines)


def _tool_decision_messages(messages: list) -> list:
    return [*messages, SystemMessage(content=_TOOL_DECISION_INSTRUCTION)]


def _build_final_response_instruction(
    *,
    messages: list,
    final_json_instruction: str | None,
    tool_calls: list[Any],
    stopped_reason: str | None,
) -> str:
    latest_request = _latest_user_request(messages)
    request_block = (
        f"\n\nLatest user request:\n<user_request>\n{latest_request}\n</user_request>"
        if latest_request
        else ""
    )
    tool_results = _tool_results_summary(tool_calls)
    tool_results_block = (
        f"\n\nTool results:\n<tool_results>\n{tool_results}\n</tool_results>"
        if tool_results
        else ""
    )
    stopped_block = ""
    if stopped_reason:
        stopped_block = (
            "\n\nTool execution was stopped before another Tool attempt because "
            f"of: {stopped_reason}. Use available successful results, explain failed "
            "parts, and request any missing identifier or input. Do not call another Tool."
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
        f"{tool_results_block}"
        f"{stopped_block}"
        "\n\nUse the Tool results block as the normalized source of truth. The final "
        "response phase intentionally receives compact results instead of raw Tool "
        "payloads. Do not omit non-Tool parts of the latest user request. Ignore any "
        "text produced during Tool decision phases; those phases are not user-facing."
        f"{json_block}"
    )


def _final_response_messages(
    messages: list,
    final_json_instruction: str | None,
    tool_calls: list[Any],
    stopped_reason: str | None,
) -> list:
    return [
        *messages,
        SystemMessage(
            content=_build_final_response_instruction(
                messages=messages,
                final_json_instruction=final_json_instruction,
                tool_calls=tool_calls,
                stopped_reason=stopped_reason,
            )
        ),
    ]


def _failure_context(
    context: dict[str, Any] | None,
    *,
    partial_result_available: bool,
) -> dict[str, Any]:
    return {
        **(context or {}),
        "partial_result_available": partial_result_available,
    }


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
    pricing_snapshot: dict[str, Any] | None = None,
) -> tuple[InstrumentedExecution, int]:
    execution = InstrumentedExecution(result=None)
    base_messages = _sanitize_base_messages(messages)
    tool_loop_messages = list(base_messages)
    call_index = 1
    result, call = await invoke_llm(
        model=model,
        messages=_tool_decision_messages(tool_loop_messages) if final_model is not None else tool_loop_messages,
        phase=initial_phase,
        call_index=call_index,
        provider=provider,
        model_name=model_name,
        pricing_snapshot=pricing_snapshot,
    )
    execution.llm_calls.append(call)
    execution.timeline.append({"kind": "llm", "occurred_at": call["occurred_at"], "payload": call})

    round_index = 0
    instruction_added = False
    consecutive_failure_rounds = 0
    stopped_reason: str | None = None

    while _has_tool_calls(result) and round_index < MAX_TOOL_ROUNDS:
        round_index += 1
        tool_loop_messages.append(result)
        tool_calls = list(getattr(result, "tool_calls", None) or [])
        started = time.monotonic()
        results = await asyncio.gather(
            *[
                execute_tool_call(
                    execute=execute_single_tool,
                    tool_call=tool_call,
                    resolved_tool_id=tool_name_to_id.get(tool_call["name"], tool_call["name"]),
                )
                for tool_call in tool_calls
            ]
        )
        execution.tool_wall_latency_ms += round((time.monotonic() - started) * 1000)
        round_failed = False
        for info, message, payload in results:
            execution.tool_calls.append(info)
            execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            execution.timeline.append({"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload})
            tool_loop_messages.append(message)
            round_failed = round_failed or info.success is False

        consecutive_failure_rounds = consecutive_failure_rounds + 1 if round_failed else 0
        if consecutive_failure_rounds >= MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS:
            stopped_reason = "repeated semantic Tool failures"
            break
        if round_index >= MAX_TOOL_ROUNDS:
            stopped_reason = "Tool round limit reached"
            break

        if final_model is None and final_json_instruction and not instruction_added:
            tool_loop_messages.append(SystemMessage(content=final_json_instruction))
            instruction_added = True

        call_index += 1
        try:
            result, call = await invoke_llm(
                model=model,
                messages=_tool_decision_messages(tool_loop_messages) if final_model is not None else tool_loop_messages,
                phase=f"tool_followup_{round_index}",
                call_index=call_index,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
            )
        except InstrumentedExecutionError as exc:
            execution.llm_calls.extend(exc.llm_calls)
            execution.timeline.extend(exc.timeline)
            execution.failure_context = _failure_context(
                exc.failure_context,
                partial_result_available=bool(execution.tool_calls),
            )
            stopped_reason = "the Tool follow-up request was rejected by the provider"
            break
        execution.llm_calls.append(call)
        execution.timeline.append({"kind": "llm", "occurred_at": call["occurred_at"], "payload": call})

    if _has_tool_calls(result) and final_model is None:
        raise InstrumentedExecutionError(
            stopped_reason or "Tool call round limit exceeded",
            llm_calls=execution.llm_calls,
            tool_calls=execution.tool_calls,
            timeline=execution.timeline,
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            failure_context=_failure_context(
                execution.failure_context,
                partial_result_available=bool(execution.tool_calls),
            ),
        )

    if final_model is not None:
        call_index += 1
        try:
            result, call = await invoke_llm(
                model=final_model,
                messages=_final_response_messages(
                    base_messages,
                    final_json_instruction,
                    execution.tool_calls,
                    stopped_reason,
                ),
                phase="final_response_generation",
                call_index=call_index,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
            )
        except InstrumentedExecutionError as exc:
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=execution.llm_calls + exc.llm_calls,
                tool_calls=execution.tool_calls,
                timeline=execution.timeline + exc.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=_failure_context(
                    exc.failure_context or execution.failure_context,
                    partial_result_available=bool(execution.tool_calls),
                ),
            ) from exc
        execution.llm_calls.append(call)
        execution.timeline.append({"kind": "llm", "occurred_at": call["occurred_at"], "payload": call})

    execution.result = result
    return execution, call_index
