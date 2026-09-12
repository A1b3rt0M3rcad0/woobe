from __future__ import annotations

import asyncio
from typing import Any

import uuid6

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.execution_instrumentation import (
    aggregate_usage,
    execute_tool_call as _execute_tool_call,
    invoke_llm as _invoke_llm,
    resolve_effective_output_tokens,
    utc_iso,
)
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.security.redaction import redact_text


async def emit_durable_execution_fact(
    event_type: str,
    payload: dict[str, Any],
    *,
    durable: bool = False,
) -> None:
    """Record a canonical execution fact when this Run owns a durable journal.

    Legacy Runs deliberately remain a no-op. Event-journal Runs fail closed when the
    recorder is missing: continuing an external operation without its canonical fact
    would recreate the execution black hole this storage mode exists to remove.
    """

    context = current_execution.get()
    if context is None or getattr(context, "storage_version", None) != EVENT_JOURNAL_STORAGE_VERSION:
        return
    recorder = getattr(context, "run_event_recorder", None)
    if recorder is None:
        raise RuntimeError("Durable Agent Run journal recorder is not bound")
    await recorder.emit(event_type, payload, durable=durable)


def _model_payload(
    call: dict[str, Any] | None,
    *,
    operation_id: str,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
) -> dict[str, Any]:
    call = dict(call or {})
    context_snapshot = call.pop("context_snapshot", None)
    payload: dict[str, Any] = {
        "operation_id": operation_id,
        "call_index": call_index,
        "phase": phase,
        "provider": provider,
        "model": model_name,
        **call,
    }
    if isinstance(context_snapshot, dict):
        payload["context_snapshot_id"] = context_snapshot.get("id")
    return payload


async def invoke_llm(**kwargs: Any) -> tuple[Any, dict[str, Any]]:
    """Invoke the existing instrumented model path with a canonical durable journal.

    Model invocation start/completion facts use the reliable Redis ingress. They do
    not add a Mongo round-trip to every provider call. Any later recovery-critical
    Tool barrier or the terminal Run barrier advances the contiguous Mongo watermark
    through these earlier model events.
    """

    operation_id = str(uuid6.uuid7())
    phase = str(kwargs["phase"])
    call_index = int(kwargs["call_index"])
    provider = str(kwargs["provider"])
    model_name = str(kwargs["model_name"])
    started_at = utc_iso()
    await emit_durable_execution_fact(
        "model.invocation.started",
        {
            "operation_id": operation_id,
            "call_index": call_index,
            "phase": phase,
            "provider": provider,
            "model": model_name,
            "status": "running",
            "started_at": started_at,
            "replay_policy": "new_attempt_allowed",
        },
    )

    try:
        result, call = await _invoke_llm(**kwargs)
    except asyncio.CancelledError:
        await emit_durable_execution_fact(
            "model.invocation.failed",
            {
                "operation_id": operation_id,
                "call_index": call_index,
                "phase": phase,
                "provider": provider,
                "model": model_name,
                "status": "cancelled",
                "failure_kind": "cancelled",
                "external_outcome": "unknown",
                "ended_at": utc_iso(),
            },
        )
        raise
    except InstrumentedExecutionError as exc:
        failure_call = exc.llm_calls[-1] if getattr(exc, "llm_calls", None) else None
        payload = _model_payload(
            failure_call,
            operation_id=operation_id,
            phase=phase,
            call_index=call_index,
            provider=provider,
            model_name=model_name,
        )
        payload["status"] = "failed"
        payload["error"] = redact_text(str(exc))
        payload["failure_context"] = dict(getattr(exc, "failure_context", None) or {})
        await emit_durable_execution_fact("model.invocation.failed", payload)
        raise
    except Exception as exc:
        await emit_durable_execution_fact(
            "model.invocation.failed",
            {
                "operation_id": operation_id,
                "call_index": call_index,
                "phase": phase,
                "provider": provider,
                "model": model_name,
                "status": "failed",
                "error": redact_text(str(exc)),
                "external_outcome": "unknown",
                "ended_at": utc_iso(),
            },
        )
        raise

    context_snapshot = call.get("context_snapshot")
    if isinstance(context_snapshot, dict):
        await emit_durable_execution_fact(
            "context.snapshot.materialized",
            {
                "operation_id": operation_id,
                "call_id": call.get("call_id"),
                "snapshot": context_snapshot,
            },
        )
    await emit_durable_execution_fact(
        "model.invocation.completed",
        {
            **_model_payload(
                call,
                operation_id=operation_id,
                phase=phase,
                call_index=call_index,
                provider=provider,
                model_name=model_name,
            ),
            "status": "completed",
            "external_outcome": "known",
        },
    )
    return result, call


async def execute_tool_call(**kwargs: Any):
    """Execute one Tool with durable before/after barriers around the side effect."""

    tool_call = kwargs["tool_call"]
    resolved_tool_id = str(kwargs["resolved_tool_id"])
    operation_id = str(tool_call["id"])
    tool_name = str(tool_call["name"])
    started_at = utc_iso()
    base = {
        "operation_id": operation_id,
        "tool_call_id": operation_id,
        "tool_name": tool_name,
        "resolved_tool_id": resolved_tool_id,
        "input": tool_call.get("args"),
        "started_at": started_at,
        "replay_policy": "requires_idempotency_or_durable_result",
    }

    # This barrier is intentional. Once this returns, recovery can prove that a Tool
    # may have received the request even if the API process disappears immediately.
    await emit_durable_execution_fact(
        "tool.call.started",
        {**base, "status": "running", "external_outcome": "pending"},
        durable=True,
    )

    try:
        info, message, payload = await _execute_tool_call(**kwargs)
    except asyncio.CancelledError:
        await emit_durable_execution_fact(
            "tool.call.failed",
            {
                **base,
                "status": "cancelled",
                "failure_kind": "cancelled",
                "external_outcome": "unknown",
                "retry_safe": False,
                "ended_at": utc_iso(),
            },
            durable=True,
        )
        raise
    except Exception as exc:
        await emit_durable_execution_fact(
            "tool.call.failed",
            {
                **base,
                "status": "error",
                "error": redact_text(str(exc)),
                "external_outcome": "unknown",
                "retry_safe": False,
                "ended_at": utc_iso(),
            },
            durable=True,
        )
        raise

    event_type = "tool.call.completed" if info.success is not False else "tool.call.failed"
    await emit_durable_execution_fact(
        event_type,
        {
            **base,
            **dict(payload),
            "status": "completed" if info.success is not False else "failed",
            "external_outcome": "known",
            "resume_policy": "reuse_durable_result",
            "retry_safe": False,
        },
        durable=True,
    )
    return info, message, payload


__all__ = [
    "aggregate_usage",
    "emit_durable_execution_fact",
    "execute_tool_call",
    "invoke_llm",
    "resolve_effective_output_tokens",
]
