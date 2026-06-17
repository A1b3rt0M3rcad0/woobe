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
) -> tuple[InstrumentedExecution, int]:
    execution = InstrumentedExecution(result=None)
    call_index = 1
    result, call = await invoke_llm(
        model=model,
        messages=messages,
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

        if final_json_instruction and not instruction_added:
            messages.append(SystemMessage(content=final_json_instruction))
            instruction_added = True

        call_index += 1
        try:
            result, call = await invoke_llm(
                model=model,
                messages=messages,
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
    execution.result = result
    return execution, call_index
