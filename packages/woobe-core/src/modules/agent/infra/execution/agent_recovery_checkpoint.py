from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution

_AGENT_CHECKPOINT_PHASES = {
    "agent_preflight_boundary",
    "agent_tool_boundary",
}
_AGENT_RESUME_POLICY = "continue_after_durable_tool_results"


def _serialize_capability_message(message: Any) -> dict[str, Any]:
    if isinstance(message, AIMessage):
        return {
            "role": "assistant",
            "content": deepcopy(message.content),
            "tool_calls": deepcopy(list(getattr(message, "tool_calls", None) or [])),
        }
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "content": deepcopy(message.content),
            "tool_call_id": str(message.tool_call_id),
            "additional_kwargs": deepcopy(message.additional_kwargs or {}),
        }
    raise ValueError(
        f"Unsupported Agent recovery capability message: {type(message).__name__}"
    )


def _restore_capability_message(value: dict[str, Any]) -> Any:
    role = value.get("role")
    if role == "assistant":
        return AIMessage(
            content=deepcopy(value.get("content") or ""),
            tool_calls=deepcopy(value.get("tool_calls") or []),
        )
    if role == "tool":
        tool_call_id = value.get("tool_call_id")
        if not tool_call_id:
            raise ValueError("Agent recovery Tool message has no tool_call_id")
        return ToolMessage(
            content=deepcopy(value.get("content") or ""),
            tool_call_id=str(tool_call_id),
            additional_kwargs=deepcopy(value.get("additional_kwargs") or {}),
        )
    raise ValueError(f"Unsupported Agent recovery message role: {role}")


def _serialize_execution(execution: InstrumentedExecution) -> dict[str, Any]:
    return {
        "tool_calls": [item.model_dump(mode="json") for item in execution.tool_calls],
        "llm_calls": deepcopy(execution.llm_calls),
        "timeline": deepcopy(execution.timeline),
        "tool_wall_latency_ms": int(execution.tool_wall_latency_ms or 0),
        "tool_call_duration_sum_ms": int(execution.tool_call_duration_sum_ms or 0),
        "failure_context": deepcopy(execution.failure_context),
    }


def _restore_execution(value: dict[str, Any]) -> InstrumentedExecution:
    return InstrumentedExecution(
        result=None,
        tool_calls=[
            ToolCallInfo.model_validate(item)
            for item in value.get("tool_calls") or []
            if isinstance(item, dict)
        ],
        llm_calls=[
            deepcopy(item)
            for item in value.get("llm_calls") or []
            if isinstance(item, dict)
        ],
        timeline=[
            deepcopy(item)
            for item in value.get("timeline") or []
            if isinstance(item, dict)
        ],
        tool_wall_latency_ms=int(value.get("tool_wall_latency_ms") or 0),
        tool_call_duration_sum_ms=int(value.get("tool_call_duration_sum_ms") or 0),
        failure_context=(
            deepcopy(value["failure_context"])
            if isinstance(value.get("failure_context"), dict)
            else None
        ),
    )


def _valid_next_phase(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value in {
        "response_generation",
        "capability_response_generation",
        "final_response_generation",
    }:
        return value
    if value.startswith("tool_followup_"):
        return value
    return None


@dataclass(frozen=True, slots=True)
class AgentExecutionResume:
    next_phase: str
    next_call_index: int
    round_index: int
    consecutive_failure_rounds: int
    stopped_reason: str | None
    capability_messages: list[Any]
    execution: InstrumentedExecution


def build_agent_checkpoint_state(
    *,
    phase: str,
    tool_loop_messages: list[Any],
    base_message_count: int,
    execution: InstrumentedExecution,
    next_phase: str,
    next_call_index: int,
    round_index: int,
    consecutive_failure_rounds: int,
    stopped_reason: str | None = None,
) -> dict[str, Any]:
    if phase not in _AGENT_CHECKPOINT_PHASES:
        raise ValueError(f"Unsupported Agent recovery checkpoint phase: {phase}")
    if _valid_next_phase(next_phase) is None:
        raise ValueError(f"Unsupported Agent recovery next phase: {next_phase}")
    if base_message_count < 0 or base_message_count > len(tool_loop_messages):
        raise ValueError("Agent recovery checkpoint base message boundary is invalid")

    return {
        "phase": phase,
        "resume_policy": _AGENT_RESUME_POLICY,
        "next_phase": next_phase,
        "next_call_index": max(1, int(next_call_index)),
        "round_index": max(0, int(round_index)),
        "consecutive_failure_rounds": max(0, int(consecutive_failure_rounds)),
        "stopped_reason": str(stopped_reason) if stopped_reason else None,
        # Only capability continuation state is persisted here. Base user/system
        # messages are reconstructed from the accepted Run/Session snapshot.
        "capability_messages": [
            _serialize_capability_message(message)
            for message in tool_loop_messages[base_message_count:]
        ],
        "execution": _serialize_execution(execution),
    }


async def checkpoint_agent_boundary(**kwargs: Any) -> None:
    context = current_execution.get()
    recorder = getattr(context, "run_event_recorder", None) if context is not None else None
    if recorder is None:
        return
    await recorder.checkpoint(build_agent_checkpoint_state(**kwargs), durable=True)


def load_agent_execution_resume(value: Any) -> AgentExecutionResume | None:
    if not isinstance(value, dict):
        return None
    if value.get("phase") not in _AGENT_CHECKPOINT_PHASES:
        return None
    if value.get("resume_policy") != _AGENT_RESUME_POLICY:
        return None
    next_phase = _valid_next_phase(value.get("next_phase"))
    if next_phase is None:
        return None

    raw_messages = value.get("capability_messages")
    raw_execution = value.get("execution")
    if not isinstance(raw_messages, list) or not isinstance(raw_execution, dict):
        return None
    try:
        messages = [
            _restore_capability_message(item)
            for item in raw_messages
            if isinstance(item, dict)
        ]
        next_call_index = int(value.get("next_call_index") or 0)
        if next_call_index <= 0:
            return None
        return AgentExecutionResume(
            next_phase=next_phase,
            next_call_index=next_call_index,
            round_index=max(0, int(value.get("round_index") or 0)),
            consecutive_failure_rounds=max(
                0,
                int(value.get("consecutive_failure_rounds") or 0),
            ),
            stopped_reason=(
                str(value["stopped_reason"])
                if value.get("stopped_reason")
                else None
            ),
            capability_messages=messages,
            execution=_restore_execution(raw_execution),
        )
    except (TypeError, ValueError):
        return None


def clone_execution(execution: InstrumentedExecution) -> InstrumentedExecution:
    return _restore_execution(_serialize_execution(execution))


__all__ = [
    "AgentExecutionResume",
    "build_agent_checkpoint_state",
    "checkpoint_agent_boundary",
    "clone_execution",
    "load_agent_execution_resume",
]
