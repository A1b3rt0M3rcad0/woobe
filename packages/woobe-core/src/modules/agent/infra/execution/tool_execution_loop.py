from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Coroutine

from langchain_core.messages import AIMessage, SystemMessage

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.agent_recovery_checkpoint import (
    checkpoint_agent_boundary,
    clone_execution,
    load_agent_execution_resume,
)
from modules.agent.infra.execution.ask_use_case import _has_tool_calls
from modules.agent.infra.execution.durable_execution_instrumentation import (
    execute_tool_call,
    invoke_llm,
)

MAX_TOOL_ROUNDS = 5
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2

_TERMINAL_RESPONSE_INSTRUCTION = (
    "Generate one single final user-facing answer for the latest user request. "
    "Fulfill every part of that request completely and in the same order the user asked. "
    "Use successful capability results exactly where relevant. Explain failed "
    "capability-dependent parts accurately and ask for missing information when required. "
    "Do not invent identifiers or fabricate successful results. Do not call capabilities. "
    "Do not mention internal execution phases."
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
    """Remove raw historical capability payloads before a new LLM execution."""
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


def _extract_capability_result(output: Any) -> Any:
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


def _capability_results_summary(tool_calls: list[Any]) -> str:
    if not tool_calls:
        return ""
    lines: list[str] = []
    for index, call in enumerate(tool_calls, start=1):
        capability_name = getattr(call, "tool_name", None) or "capability"
        capability_input = getattr(call, "input", None)
        output = getattr(call, "output", None)
        success = getattr(call, "success", None)
        error_code = getattr(call, "error_code", None)
        error = getattr(call, "error", None)
        result = _extract_capability_result(output)
        status = "success" if success is not False else "failed"
        input_preview = _json_preview(capability_input) if capability_input is not None else "{}"
        if success is False:
            code = f" [{error_code}]" if error_code else ""
            result_preview = f"error{code}: {error or 'Capability execution failed'}"
        else:
            result_preview = _json_preview(result)
        lines.append(
            f"{index}. {capability_name}({input_preview}) -> {status}: {result_preview}"
        )
    return "\n".join(lines)


def _build_terminal_response_instruction(
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
    capability_results = _capability_results_summary(tool_calls)
    capability_results_block = (
        "\n\nCapability results:\n"
        f"<capability_results>\n{capability_results}\n</capability_results>"
        if capability_results
        else ""
    )
    stopped_block = ""
    if stopped_reason:
        stopped_block = (
            "\n\nCapability execution was stopped before another attempt because of: "
            f"{stopped_reason}. Use available successful results, explain failed parts, "
            "and request any missing identifier or input. Do not call another capability."
        )
    json_block = (
        "\n\nStructured output requirement:\n"
        f"{final_json_instruction}"
        if final_json_instruction
        else ""
    )
    return (
        f"{_TERMINAL_RESPONSE_INSTRUCTION}"
        f"{request_block}"
        f"{capability_results_block}"
        f"{stopped_block}"
        "\n\nUse the capability results block as the normalized source of truth. "
        "The terminal response intentionally receives compact results instead of raw "
        "capability payloads. Do not omit non-capability parts of the latest user request."
        f"{json_block}"
    )


def _terminal_response_messages(
    messages: list,
    final_json_instruction: str | None,
    tool_calls: list[Any],
    stopped_reason: str | None,
) -> list:
    return [
        *messages,
        SystemMessage(
            content=_build_terminal_response_instruction(
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


async def _invoke_terminal_recovery(
    *,
    execution: InstrumentedExecution,
    base_messages: list,
    stopped_reason: str,
    call_index: int,
    final_model: Any | None,
    final_model_factory: Callable[[], Any] | None,
    final_json_instruction: str | None,
    provider: str,
    model_name: str,
    pricing_snapshot: dict[str, Any] | None,
    context_assembler: ContextAssembler | None,
) -> Any:
    terminal_model = final_model
    if terminal_model is None and final_model_factory is not None:
        terminal_model = final_model_factory()
    if terminal_model is None:
        raise InstrumentedExecutionError(
            stopped_reason,
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

    try:
        result, call = await invoke_llm(
            model=terminal_model,
            messages=_terminal_response_messages(
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
            context_assembler=context_assembler,
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
    execution.timeline.append(
        {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
    )
    return result


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
    initial_tool_call: dict[str, Any] | None = None,
    final_model: Any | None = None,
    final_model_factory: Callable[[], Any] | None = None,
    pricing_snapshot: dict[str, Any] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> tuple[InstrumentedExecution, int]:
    """Execute or safely resume one capability-aware Agent model loop."""

    base_messages = _sanitize_base_messages(messages)
    base_message_count = len(base_messages)
    context = current_execution.get()
    resume = load_agent_execution_resume(
        getattr(context, "resume_state", None) if context is not None else None
    )

    if resume is not None:
        execution = resume.execution
        tool_loop_messages = [*base_messages, *resume.capability_messages]
        round_index = resume.round_index
        consecutive_failure_rounds = resume.consecutive_failure_rounds
        stopped_reason = resume.stopped_reason
        call_index = resume.next_call_index
        # Keep the live failure/fallback accumulator aware of the previous durable
        # attempt without sharing the same mutable instance used by this loop.
        if context is not None:
            context.execution = clone_execution(execution)
            context.resume_state = None

        if resume.next_phase == "final_response_generation":
            if not stopped_reason:
                raise InstrumentedExecutionError(
                    "Agent recovery checkpoint is missing terminal stop reason",
                    llm_calls=execution.llm_calls,
                    tool_calls=execution.tool_calls,
                    timeline=execution.timeline,
                )
            result = await _invoke_terminal_recovery(
                execution=execution,
                base_messages=base_messages,
                stopped_reason=stopped_reason,
                call_index=call_index,
                final_model=final_model,
                final_model_factory=final_model_factory,
                final_json_instruction=final_json_instruction,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
                context_assembler=context_assembler,
            )
            execution.result = result
            return execution, call_index

        result, call = await invoke_llm(
            model=model,
            messages=tool_loop_messages,
            phase=resume.next_phase,
            call_index=call_index,
            provider=provider,
            model_name=model_name,
            pricing_snapshot=pricing_snapshot,
            context_assembler=context_assembler,
        )
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )
    else:
        execution = InstrumentedExecution(result=None)
        tool_loop_messages = list(base_messages)
        round_index = 0
        consecutive_failure_rounds = 0
        stopped_reason: str | None = None
        call_index = 1

        if initial_tool_call is not None:
            preflight = AIMessage(content="", tool_calls=[initial_tool_call])
            tool_loop_messages.append(preflight)
            started = time.monotonic()
            info, message, payload = await execute_tool_call(
                execute=execute_single_tool,
                tool_call=initial_tool_call,
                resolved_tool_id=tool_name_to_id.get(
                    initial_tool_call["name"], initial_tool_call["name"]
                ),
            )
            execution.tool_wall_latency_ms += round((time.monotonic() - started) * 1000)
            execution.tool_calls.append(info)
            execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            tool_loop_messages.append(message)
            await checkpoint_agent_boundary(
                phase="agent_preflight_boundary",
                tool_loop_messages=tool_loop_messages,
                base_message_count=base_message_count,
                execution=execution,
                next_phase=initial_phase,
                next_call_index=1,
                round_index=0,
                consecutive_failure_rounds=0,
            )

        result, call = await invoke_llm(
            model=model,
            messages=tool_loop_messages,
            phase=initial_phase,
            call_index=call_index,
            provider=provider,
            model_name=model_name,
            pricing_snapshot=pricing_snapshot,
            context_assembler=context_assembler,
        )
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

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
                    resolved_tool_id=tool_name_to_id.get(
                        tool_call["name"], tool_call["name"]
                    ),
                )
                for tool_call in tool_calls
            ]
        )
        execution.tool_wall_latency_ms += round((time.monotonic() - started) * 1000)
        round_failed = False
        for info, message, payload in results:
            execution.tool_calls.append(info)
            execution.tool_call_duration_sum_ms += int(info.duration_ms or 0)
            execution.timeline.append(
                {"kind": "tool", "occurred_at": payload["occurred_at"], "payload": payload}
            )
            tool_loop_messages.append(message)
            round_failed = round_failed or info.success is False

        consecutive_failure_rounds = (
            consecutive_failure_rounds + 1 if round_failed else 0
        )
        stopped_reason = None
        if consecutive_failure_rounds >= MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS:
            stopped_reason = "repeated semantic capability failures"
        elif round_index >= MAX_TOOL_ROUNDS:
            stopped_reason = "capability round limit reached"

        next_call_index = call_index + 1
        next_phase = (
            "final_response_generation"
            if stopped_reason
            else f"tool_followup_{round_index}"
        )
        # All Tool results in this boundary were durably journaled by
        # execute_tool_call before it returned. Persist the continuation state before
        # allowing the next provider invocation to begin.
        await checkpoint_agent_boundary(
            phase="agent_tool_boundary",
            tool_loop_messages=tool_loop_messages,
            base_message_count=base_message_count,
            execution=execution,
            next_phase=next_phase,
            next_call_index=next_call_index,
            round_index=round_index,
            consecutive_failure_rounds=consecutive_failure_rounds,
            stopped_reason=stopped_reason,
        )
        if stopped_reason:
            break

        call_index = next_call_index
        try:
            result, call = await invoke_llm(
                model=model,
                messages=tool_loop_messages,
                phase=next_phase,
                call_index=call_index,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
                context_assembler=context_assembler,
            )
        except InstrumentedExecutionError as exc:
            execution.llm_calls.extend(exc.llm_calls)
            execution.timeline.extend(exc.timeline)
            execution.failure_context = _failure_context(
                exc.failure_context,
                partial_result_available=bool(execution.tool_calls),
            )
            stopped_reason = (
                "the capability follow-up request was rejected by the provider"
            )
            break
        execution.llm_calls.append(call)
        execution.timeline.append(
            {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
        )

    requires_terminal_recovery = bool(stopped_reason) and _has_tool_calls(result)
    if requires_terminal_recovery:
        call_index += 1
        result = await _invoke_terminal_recovery(
            execution=execution,
            base_messages=base_messages,
            stopped_reason=stopped_reason or "Capability execution could not complete",
            call_index=call_index,
            final_model=final_model,
            final_model_factory=final_model_factory,
            final_json_instruction=final_json_instruction,
            provider=provider,
            model_name=model_name,
            pricing_snapshot=pricing_snapshot,
            context_assembler=context_assembler,
        )

    execution.result = result
    return execution, call_index
