from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any
from uuid import UUID

from shared.contracts.run_event_journal import DurableRunEvent, RunEventJournalPort
from shared.runtime.projection import initial_projection, reduce_projection

logger = logging.getLogger(__name__)


_TERMINAL_STATUS_BY_EVENT = {
    "run.completed": "completed",
    "run.failed": "failed",
    "run.cancelled": "cancelled",
    "run.timed_out": "timed_out",
    "run.uncertain": "uncertain",
}


def _pick(source: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: source[key] for key in keys if source.get(key) is not None}


def _invocation_payload(event: DurableRunEvent) -> dict[str, Any]:
    payload = event.payload
    nested = payload.get("invocation")
    invocation = nested if isinstance(nested, dict) else {}
    merged = {**invocation, **payload}
    if merged.get("invocation_id") is None:
        merged["invocation_id"] = event.metadata.get("invocation_id")
    return merged


def _public_runtime_event(
    event: DurableRunEvent,
) -> tuple[str, dict[str, Any]] | None:
    """Translate a canonical durable fact into the public runtime projection language.

    This is deliberately an allow-list. Journal payloads may contain internal execution
    evidence; replay for SSE must never expose raw prompts, Tool inputs/outputs,
    credentials, provider errors or hidden reasoning.
    """

    event_type = event.event_type
    payload = event.payload

    if event_type in {"run.attempt.started", "execution.started"}:
        return "execution_started", {}

    if event_type == "output.delta.batch":
        content = payload.get("content")
        if not isinstance(content, str) or not content:
            return None
        return "token", {
            "content": content,
            "visibility": "assistant",
            "channel": "final",
        }

    if event_type == "output.retracted":
        size = payload.get("content_length")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            return None
        return "token_retract", {"content_length": size}

    if event_type in {"tool.call.started", "tool.call.completed", "tool.call.failed"}:
        source = _invocation_payload(event)
        tool_call_id = source.get("tool_call_id") or source.get("id")
        tool_name = source.get("tool_name") or source.get("name")
        public = _pick(
            source,
            "invocation_id",
            "skill_name",
            "skill_version",
            "duration_ms",
            "error_code",
            "started_at",
            "ended_at",
        )
        if tool_call_id is not None:
            public["tool_call_id"] = str(tool_call_id)
        if tool_name is not None:
            public["tool_name"] = str(tool_name)
        if event_type == "tool.call.started":
            return "tool_call_started", public
        public["success"] = event_type == "tool.call.completed" and source.get(
            "success", True
        ) is not False
        public["status"] = (
            source.get("status")
            or ("success" if public["success"] else "error")
        )
        return "tool_call_completed", public

    if event_type.startswith("agent.invocation."):
        source = _invocation_payload(event)
        public = _pick(
            source,
            "invocation_id",
            "agent_run_id",
            "parent_invocation_id",
            "node_id",
            "agent_id",
            "depth",
            "label",
            "provider",
            "model",
            "source",
            "version",
            "session_mode",
            "agent_session_id",
            "context_state",
            "previous_invocation_count",
            "started_at",
            "completed_at",
            "trace_id",
            "usage",
        )
        suffix = event_type.removeprefix("agent.invocation.")
        mapped = {
            "started": "agent_invocation_started",
            "completed": "agent_invocation_completed",
            "failed": "agent_invocation_failed",
            "cancelled": "agent_invocation_cancelled",
        }.get(suffix)
        if mapped is None:
            return None
        if suffix == "failed":
            failure = source.get("failure")
            if isinstance(failure, dict):
                public.update(_pick(failure, "code", "stage", "retryable"))
        return mapped, public

    if event_type.startswith("delegation."):
        suffix = event_type.removeprefix("delegation.")
        mapped = {
            "started": "delegation_started",
            "completed": "delegation_completed",
            "failed": "delegation_failed",
            "skipped": "delegation_skipped",
        }.get(suffix)
        if mapped is None:
            return None
        return mapped, _pick(
            payload,
            "invocation_id",
            "parent_invocation_id",
            "target_node_id",
            "target",
            "task_fingerprint",
            "reason",
        )

    if event_type == "run.completed":
        answer = payload.get("answer")
        if not isinstance(answer, str):
            answer = payload.get("output") if isinstance(payload.get("output"), str) else ""
        public = {
            "output": answer,
            **_pick(
                payload,
                "trace_id",
                "usage",
                "parsed_output",
                "output_parse_error",
                "completed_at",
            ),
        }
        public["result"] = {
            "answer": answer,
            **_pick(payload, "parsed_output", "output_parse_error"),
        }
        return "execution_completed", public

    if event_type == "run.cancelled":
        output = payload.get("answer")
        if not isinstance(output, str):
            output = payload.get("output") if isinstance(payload.get("output"), str) else ""
        return "execution_cancelled", {
            "output": output,
            "partial": bool(payload.get("partial") or output),
            "cancelled": True,
            "result": {
                "answer": output,
                "partial": bool(payload.get("partial") or output),
                "cancelled": True,
            },
            **_pick(payload, "trace_id", "usage", "completed_at"),
        }

    if event_type in {"run.failed", "run.timed_out", "run.uncertain"}:
        output = payload.get("output") if isinstance(payload.get("output"), str) else ""
        return "execution_failed", {
            "output": output,
            "partial": bool(output),
            "failure_code": payload.get("failure_code"),
            "trace_id": payload.get("trace_id"),
            "uncertain": event_type == "run.uncertain" or bool(payload.get("uncertain")),
            "partial_result_available": bool(
                payload.get("partial_result_available") or output
            ),
        }

    # Model/context/checkpoint/fallback facts remain internal evidence. They still
    # advance the logical sequence below, but do not become public SSE payloads.
    return None


async def journal_runtime_state(
    journal: RunEventJournalPort | None,
    run_id: UUID,
    run_kind: str,
    *,
    base_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Rebuild the public Run projection from Mongo's contiguous durable prefix.

    PostgreSQL is accepted as a metadata/read-model seed only. Once a journal exists,
    output/status are reconstructed from the journal so a lagging SQL projector cannot
    duplicate output or mask a durable terminal fact.
    """

    base = deepcopy(base_state) if isinstance(base_state, dict) else None
    if journal is None:
        return base

    try:
        journal_state = await journal.get_state(run_id)
    except Exception as exc:
        logger.warning("Run journal state unavailable run_id=%s: %s", run_id, exc)
        return base

    if (
        journal_state is None
        or journal_state.durable_sequence <= 0
        or str(journal_state.run_kind).lower() != run_kind.lower()
    ):
        return base

    seed = deepcopy(base) if base is not None else {}
    seed.update({"status": "running", "output": "", "result": None, "usage": {}})
    projection = initial_projection(run_id, run_kind, seed)

    durable_sequence = int(journal_state.durable_sequence)
    expected = 1
    after_sequence = 0
    try:
        while after_sequence < durable_sequence:
            events = await journal.list_events(
                run_id,
                after_sequence=after_sequence,
                through_sequence=durable_sequence,
                limit=1000,
            )
            if not events:
                logger.warning(
                    "Run journal replay stopped before durable watermark run_id=%s "
                    "after=%s durable=%s",
                    run_id,
                    after_sequence,
                    durable_sequence,
                )
                return base

            for event in events:
                if event.sequence != expected:
                    logger.warning(
                        "Run journal replay sequence gap run_id=%s expected=%s observed=%s",
                        run_id,
                        expected,
                        event.sequence,
                    )
                    return base
                mapped = _public_runtime_event(event)
                if mapped is not None:
                    public_type, public_payload = mapped
                    projection = reduce_projection(
                        projection,
                        public_type,
                        public_payload,
                        sequence=event.sequence,
                        occurred_at=event.occurred_at,
                    )
                else:
                    projection["sequence"] = event.sequence
                    projection["updated_at"] = event.occurred_at
                expected += 1
                after_sequence = event.sequence
    except Exception as exc:
        logger.warning("Run journal replay unavailable run_id=%s: %s", run_id, exc)
        return base

    if after_sequence != durable_sequence:
        return base

    terminal_status = journal_state.terminal_status
    if terminal_status is not None:
        projection["status"] = terminal_status
    projection.update(
        {
            "run_id": str(run_id),
            "kind": run_kind.upper(),
            "sequence": durable_sequence,
            "realtime_available": False,
            "durable_source": "mongodb_journal",
            "journal_durable_sequence": durable_sequence,
        }
    )
    return projection


__all__ = ["journal_runtime_state"]
