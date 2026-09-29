from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import SourceInfo, ToolCallInfo
from modules.agent.application.interfaces.execution import (
    ExecutionSuspension,
    InstrumentedExecution,
)
from modules.agent.application.interfaces.execution_context import current_execution

_AGENT_CHECKPOINT_PHASES = {
    "agent_preflight_boundary",
    "agent_tool_boundary",
}
_AGENT_RESUME_POLICY = "continue_after_durable_tool_results"
_STRATEGY_RESUME_POLICY = "continue_execution_strategy"


def _serialize_capability_message(message: Any) -> dict[str, Any]:
    if isinstance(message, AIMessage):
        return {
            "role": "assistant",
            "id": str(message.id) if getattr(message, "id", None) is not None else None,
            "content": deepcopy(message.content),
            "tool_calls": deepcopy(list(getattr(message, "tool_calls", None) or [])),
        }
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "id": str(message.id) if getattr(message, "id", None) is not None else None,
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
            id=(str(value["id"]) if value.get("id") is not None else None),
            content=deepcopy(value.get("content") or ""),
            tool_calls=deepcopy(value.get("tool_calls") or []),
        )
    if role == "tool":
        tool_call_id = value.get("tool_call_id")
        if not tool_call_id:
            raise ValueError("Agent recovery Tool message has no tool_call_id")
        return ToolMessage(
            id=(str(value["id"]) if value.get("id") is not None else None),
            content=deepcopy(value.get("content") or ""),
            tool_call_id=str(tool_call_id),
            additional_kwargs=deepcopy(value.get("additional_kwargs") or {}),
        )
    raise ValueError(f"Unsupported Agent recovery message role: {role}")


def _serialize_execution(execution: InstrumentedExecution) -> dict[str, Any]:
    return {
        "tool_calls": [item.model_dump(mode="json") for item in execution.tool_calls],
        "llm_calls": deepcopy(execution.llm_calls),
        "knowledge_calls": deepcopy(execution.knowledge_calls),
        "sources": [item.model_dump(mode="json") for item in execution.sources],
        "timeline": deepcopy(execution.timeline),
        "tool_wall_latency_ms": int(execution.tool_wall_latency_ms or 0),
        "tool_call_duration_sum_ms": int(execution.tool_call_duration_sum_ms or 0),
        "failure_context": deepcopy(execution.failure_context),
        "fallback_used": bool(execution.fallback_used),
        "fallback_info": deepcopy(execution.fallback_info),
        "suspension": (
            {
                "reason": execution.suspension.reason,
                "operation_ref": execution.suspension.operation_ref,
                "metadata": deepcopy(execution.suspension.metadata),
            }
            if execution.suspension is not None
            else None
        ),
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
        knowledge_calls=[
            deepcopy(item)
            for item in value.get("knowledge_calls") or []
            if isinstance(item, dict)
        ],
        sources=[
            SourceInfo.model_validate(item)
            for item in value.get("sources") or []
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
        fallback_used=bool(value.get("fallback_used")),
        fallback_info=(
            deepcopy(value["fallback_info"])
            if isinstance(value.get("fallback_info"), dict)
            else None
        ),
        suspension=(
            ExecutionSuspension(
                reason=str(value["suspension"].get("reason") or ""),
                operation_ref=(
                    str(value["suspension"]["operation_ref"])
                    if value["suspension"].get("operation_ref") is not None
                    else None
                ),
                metadata=(
                    deepcopy(value["suspension"].get("metadata"))
                    if isinstance(value["suspension"].get("metadata"), dict)
                    else None
                ),
            )
            if isinstance(value.get("suspension"), dict)
            and value["suspension"].get("reason")
            else None
        ),
    )


def _restore_checkpoint_messages(value: Any) -> list[Any] | None:
    if not isinstance(value, list):
        return None
    try:
        return [
            _restore_capability_message(item)
            for item in value
            if isinstance(item, dict)
        ]
    except (TypeError, ValueError):
        return None


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
class StrategyExecutionResume:
    """Opaque strategy continuation restored from a durable execution boundary."""

    strategy_name: str
    phase: str
    cursor: dict[str, Any]
    capability_messages: list[Any]
    context_contributions: dict[str, dict[str, Any]]
    execution: InstrumentedExecution


@dataclass(frozen=True, slots=True)
class AgentExecutionResume:
    """Legacy Standard-loop view kept for backwards-compatible callers/tests."""

    next_phase: str
    next_call_index: int
    round_index: int
    consecutive_failure_rounds: int
    stopped_reason: str | None
    capability_messages: list[Any]
    execution: InstrumentedExecution


def build_strategy_checkpoint_state(
    *,
    strategy_name: str,
    phase: str,
    messages: list[Any],
    base_message_count: int,
    execution: InstrumentedExecution,
    cursor: dict[str, Any],
    context_contributions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a strategy-neutral durable continuation snapshot.

    `cursor` belongs to the concrete Strategy. Recovery infrastructure persists it as an
    opaque JSON-compatible mapping and never needs to understand loop semantics.
    """
    strategy_name = strategy_name.strip()
    phase = phase.strip()
    if not strategy_name:
        raise ValueError("Execution Strategy checkpoint requires strategy_name")
    if not phase:
        raise ValueError("Execution Strategy checkpoint requires phase")
    if base_message_count < 0 or base_message_count > len(messages):
        raise ValueError("Execution Strategy checkpoint base message boundary is invalid")
    if not isinstance(cursor, dict):
        raise ValueError("Execution Strategy checkpoint cursor must be a mapping")

    return {
        "phase": phase,
        "resume_policy": _STRATEGY_RESUME_POLICY,
        "execution_strategy": strategy_name,
        "strategy_cursor": deepcopy(cursor),
        "context_contributions": deepcopy(context_contributions or {}),
        "capability_messages": [
            _serialize_capability_message(message)
            for message in messages[base_message_count:]
        ],
        "execution": _serialize_execution(execution),
    }


async def checkpoint_strategy_boundary(**kwargs: Any) -> None:
    context = current_execution.get()
    recorder = getattr(context, "run_event_recorder", None) if context is not None else None
    if recorder is None:
        return
    await recorder.checkpoint(build_strategy_checkpoint_state(**kwargs), durable=True)


def load_strategy_execution_resume(
    value: Any,
    *,
    strategy_name: str,
) -> StrategyExecutionResume | None:
    """Load a generic Strategy checkpoint, with legacy Standard checkpoint support."""
    if not isinstance(value, dict):
        return None

    if value.get("resume_policy") == _STRATEGY_RESUME_POLICY:
        stored_strategy = value.get("execution_strategy")
        phase = value.get("phase")
        cursor = value.get("strategy_cursor")
        raw_execution = value.get("execution")
        raw_context_contributions = value.get("context_contributions") or {}
        messages = _restore_checkpoint_messages(value.get("capability_messages"))
        if (
            stored_strategy != strategy_name
            or not isinstance(phase, str)
            or not phase
            or not isinstance(cursor, dict)
            or not isinstance(raw_execution, dict)
            or not isinstance(raw_context_contributions, dict)
            or any(
                not isinstance(key, str) or not isinstance(item, dict)
                for key, item in raw_context_contributions.items()
            )
            or messages is None
        ):
            return None
        try:
            return StrategyExecutionResume(
                strategy_name=strategy_name,
                phase=phase,
                cursor=deepcopy(cursor),
                capability_messages=messages,
                context_contributions=deepcopy(raw_context_contributions),
                execution=_restore_execution(raw_execution),
            )
        except (TypeError, ValueError):
            return None

    if strategy_name != "standard":
        return None
    legacy = load_agent_execution_resume(value)
    if legacy is None:
        return None
    return StrategyExecutionResume(
        strategy_name="standard",
        phase=str(value.get("phase") or "agent_tool_boundary"),
        cursor={
            "next_phase": legacy.next_phase,
            "next_call_index": legacy.next_call_index,
            "round_index": legacy.round_index,
            "consecutive_failure_rounds": legacy.consecutive_failure_rounds,
            "stopped_reason": legacy.stopped_reason,
        },
        capability_messages=legacy.capability_messages,
        context_contributions={},
        execution=legacy.execution,
    )


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
    """Build the legacy Standard checkpoint shape for backwards compatibility."""
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

    raw_execution = value.get("execution")
    messages = _restore_checkpoint_messages(value.get("capability_messages"))
    if not isinstance(raw_execution, dict) or messages is None:
        return None
    try:
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
    "StrategyExecutionResume",
    "build_agent_checkpoint_state",
    "build_strategy_checkpoint_state",
    "checkpoint_agent_boundary",
    "checkpoint_strategy_boundary",
    "clone_execution",
    "load_agent_execution_resume",
    "load_strategy_execution_resume",
]
