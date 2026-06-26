from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from langchain_core.messages import ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.application.use_cases.runtime_streaming import (
    emit_agent_activity,
    emit_runtime_event,
    invoke_model_with_optional_streaming,
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InstrumentedExecution:
    result: Any
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCallInfo] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    tool_wall_latency_ms: int = 0
    tool_call_duration_sum_ms: int = 0


class InstrumentedExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        llm_calls: list[dict[str, Any]] | None = None,
        tool_calls: list[ToolCallInfo] | None = None,
        timeline: list[dict[str, Any]] | None = None,
        tool_wall_latency_ms: int = 0,
        tool_call_duration_sum_ms: int = 0,
    ) -> None:
        super().__init__(message)
        self.llm_calls = llm_calls or []
        self.tool_calls = tool_calls or []
        self.timeline = timeline or []
        self.tool_wall_latency_ms = tool_wall_latency_ms
        self.tool_call_duration_sum_ms = tool_call_duration_sum_ms


def _usage_from_result(result: Any) -> dict[str, int | None]:
    usage = getattr(result, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def _serialized_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


def tool_http_latency_ms(output: Any) -> int | None:
    if not isinstance(output, dict):
        return None
    meta = output.get("metadata")
    if isinstance(meta, dict):
        latency = meta.get("latency_ms")
        if isinstance(latency, int | float):
            return round(latency)
    return None


async def invoke_llm(
    *,
    model: Any,
    messages: list,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
) -> tuple[Any, dict[str, Any]]:
    started_at = utc_iso()
    started = time.monotonic()
    try:
        result = await invoke_model_with_optional_streaming(
            model=model,
            messages=messages,
            phase=phase,
            provider=provider,
            model_name=model_name,
        )
    except Exception as exc:
        ended_at = utc_iso()
        duration_ms = round((time.monotonic() - started) * 1000)
        call = {
            "call_index": call_index,
            "provider": provider,
            "model": model_name,
            "phase": phase,
            "status": "error",
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "occurred_at": ended_at,
            "error": str(exc),
        }
        raise InstrumentedExecutionError(
            str(exc),
            llm_calls=[call],
            timeline=[{"kind": "llm", "occurred_at": ended_at, "payload": call}],
        ) from exc

    ended_at = utc_iso()
    duration_ms = round((time.monotonic() - started) * 1000)
    usage = _usage_from_result(result)
    call = {
        "call_index": call_index,
        "provider": provider,
        "model": model_name,
        "phase": phase,
        "status": "success",
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "occurred_at": ended_at,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "response_preview": _serialized_text(result)[:500],
    }
    return result, call


async def execute_tool_call(
    *,
    execute: Callable[[dict, str], Awaitable[dict]],
    tool_call: dict,
    resolved_tool_id: str,
) -> tuple[ToolCallInfo, ToolMessage, dict[str, Any]]:
    started_at = utc_iso()
    tool_name = tool_call["name"]
    await emit_agent_activity(
        "calling_tool",
        message=f"Chamando ferramenta: {tool_name}...",
        tool_name=tool_name,
    )
    await emit_runtime_event(
        "tool_call_started",
        tool_call_id=tool_call["id"],
        tool_name=tool_name,
        input=tool_call.get("args"),
        status="running",
        started_at=started_at,
    )
    started = time.monotonic()
    output = await execute(tool_call, resolved_tool_id)
    ended_at = utc_iso()
    duration_ms = round((time.monotonic() - started) * 1000)
    success = output.get("success", False) if isinstance(output, dict) else True
    error = output.get("error") if isinstance(output, dict) else None
    info = ToolCallInfo(
        tool_call_id=tool_call["id"],
        tool_name=tool_name,
        input=tool_call.get("args"),
        output=output,
        duration_ms=duration_ms,
        success=success,
        error=error,
    )
    message = ToolMessage(
        content=json.dumps(output) if isinstance(output, dict) else str(output),
        tool_call_id=tool_call["id"],
    )
    payload = {
        "tool_call_id": tool_call["id"],
        "tool_name": tool_name,
        "input": tool_call.get("args"),
        "output": output,
        "duration_ms": duration_ms,
        "http_latency_ms": tool_http_latency_ms(output),
        "success": success,
        "error": error,
        "status": "success" if success else "error",
        "started_at": started_at,
        "ended_at": ended_at,
        "occurred_at": ended_at,
    }
    await emit_runtime_event("tool_call_completed", **payload)
    await emit_agent_activity(
        "processing_tool_result",
        message="Processando resultado da ferramenta...",
        tool_name=tool_name,
    )
    return info, message, payload
