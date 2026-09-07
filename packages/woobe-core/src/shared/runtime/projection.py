from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.contracts.execution_state import ExecutionEvent

TERMINAL_RUNTIME_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "timed_out",
    "uncertain",
}
STRUCTURAL_RUNTIME_EVENTS = {
    "agent.run.accepted",
    "execution_started",
    "agent_invocation_started",
    "agent_invocation_completed",
    "agent_invocation_failed",
    "agent_invocation_cancelled",
    "delegation_started",
    "delegation_completed",
    "delegation_failed",
    "delegation_skipped",
    "tool_call_started",
    "tool_call_completed",
    "usage",
    "done",
    "error",
    "cancelled",
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _as_record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _upsert_by_key(
    values: list[dict[str, Any]],
    *,
    key: str,
    key_value: str,
    update: dict[str, Any],
) -> list[dict[str, Any]]:
    found = False
    result: list[dict[str, Any]] = []
    for value in values:
        if str(value.get(key) or "") == key_value:
            result.append({**value, **deepcopy(update)})
            found = True
        else:
            result.append(value)
    if not found:
        result.append(deepcopy(update))
    return result


def _delegation_key(payload: dict[str, Any]) -> str | None:
    fingerprint = payload.get("task_fingerprint")
    if fingerprint:
        return str(fingerprint)
    parent = payload.get("invocation_id")
    target = payload.get("target_node_id") or payload.get("target")
    if parent and target:
        return f"{parent}:{target}"
    return None


def _tool_name(payload: dict[str, Any]) -> str | None:
    value = payload.get("tool_name") or payload.get("name")
    return str(value) if value else None


def _is_delegation_tool(payload: dict[str, Any]) -> bool:
    name = _tool_name(payload)
    return bool(name and name.startswith("delegate_to_"))


def _tool_key(payload: dict[str, Any]) -> str | None:
    tool_call_id = payload.get("tool_call_id") or payload.get("id")
    if tool_call_id:
        return str(tool_call_id)
    invocation_id = payload.get("invocation_id")
    name = _tool_name(payload)
    if invocation_id and name:
        return f"{invocation_id}:{name}"
    return None


def initial_projection(
    run_id: UUID,
    run_kind: str,
    hot_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = hot_state or {}
    root_result = state.get("root_result")
    root_result = root_result if isinstance(root_result, dict) else {}
    terminal_result = state.get("terminal_result")
    terminal_result = terminal_result if isinstance(terminal_result, dict) else {}
    status = str(state.get("status") or "running")
    if status == "terminal_pending_persist":
        status = "running"
    output = (
        root_result.get("answer")
        or terminal_result.get("output")
        or terminal_result.get("answer")
        or ""
    )
    parsed_output = (
        root_result.get("parsed_output")
        if "parsed_output" in root_result
        else terminal_result.get("parsed_output")
    )
    output_parse_error = (
        root_result.get("output_parse_error")
        if "output_parse_error" in root_result
        else terminal_result.get("output_parse_error")
    )
    return {
        "run_id": str(run_id),
        "kind": run_kind.upper(),
        "status": status,
        "sequence": 0,
        "output": str(output or ""),
        "activity": None,
        "active_tools": [],
        "tools": [],
        "active_agents": [],
        "completed_agents": [],
        "cancelled_agents": [],
        "invocations": [],
        "delegations": [],
        "current_route": None,
        "usage": state.get("usage") if isinstance(state.get("usage"), dict) else {},
        "result": root_result or terminal_result or None,
        "parsed_output": parsed_output,
        "output_parse_error": output_parse_error,
        "updated_at": state.get("updated_at") or _now_iso(),
        "realtime_available": True,
    }


def public_event(event: ExecutionEvent) -> tuple[str, dict[str, Any]]:
    payload = deepcopy(event.payload)
    visibility = str(payload.get("visibility") or "public").lower()
    if visibility in {"internal", "private", "debug"}:
        return "run.progress", {}

    if event.event_type == "token":
        if (
            payload.get("visibility", "assistant") != "assistant"
            or payload.get("channel", "final") != "final"
        ):
            return "run.progress", {}
        return event.event_type, payload

    if (
        event.event_type in {"tool_call_started", "tool_call_completed"}
        and _is_delegation_tool(payload)
    ):
        return "run.progress", {}

    if event.event_type == "tool_call_started":
        for key in ("input", "arguments", "headers", "authorization"):
            payload.pop(key, None)
    elif event.event_type == "tool_call_completed":
        for key in ("output", "result", "response", "headers", "authorization"):
            payload.pop(key, None)
    elif event.event_type == "agent_invocation_completed":
        for key in ("output", "parsed_output", "tool_calls", "sources"):
            payload.pop(key, None)

    return event.event_type, payload


def reduce_projection(
    projection: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    *,
    sequence: int,
    occurred_at: str,
) -> dict[str, Any]:
    state = deepcopy(projection)
    state["sequence"] = sequence
    state["updated_at"] = occurred_at or _now_iso()

    if event_type in {"agent.run.accepted", "execution_started"}:
        state["status"] = "running"
    elif event_type == "meta":
        for key in ("trace_id", "session_id", "agent_id", "project_id"):
            if payload.get(key) is not None:
                state[key] = payload[key]
    elif event_type == "token":
        content = payload.get("content")
        if isinstance(content, str):
            state["output"] = str(state.get("output") or "") + content
    elif event_type == "token_retract":
        size = int(payload.get("content_length") or 0)
        if size > 0:
            output = str(state.get("output") or "")
            state["output"] = output[:-size] if size < len(output) else ""
    elif event_type == "agent_activity":
        state["activity"] = {
            key: payload.get(key)
            for key in ("status", "phase", "message", "tool_name")
            if payload.get(key) is not None
        }
    elif event_type == "tool_call_started":
        tool_name = _tool_name(payload)
        tool_key = _tool_key(payload)
        if tool_name and tool_key:
            active = set(_as_list(state.get("active_tools")))
            active.add(tool_key)
            state["active_tools"] = sorted(active)
            state["tools"] = _upsert_by_key(
                _as_record_list(state.get("tools")),
                key="id",
                key_value=tool_key,
                update={
                    "id": tool_key,
                    "tool_call_id": str(payload.get("tool_call_id") or tool_key),
                    "invocation_id": (
                        str(payload["invocation_id"])
                        if payload.get("invocation_id")
                        else None
                    ),
                    "tool_name": tool_name,
                    "status": "running",
                    "success": None,
                    "started_at": payload.get("started_at") or occurred_at,
                },
            )
    elif event_type == "tool_call_completed":
        tool_name = _tool_name(payload)
        tool_key = _tool_key(payload)
        if tool_name and tool_key:
            active = set(_as_list(state.get("active_tools")))
            active.discard(tool_key)
            state["active_tools"] = sorted(active)
            state["tools"] = _upsert_by_key(
                _as_record_list(state.get("tools")),
                key="id",
                key_value=tool_key,
                update={
                    "id": tool_key,
                    "tool_call_id": str(payload.get("tool_call_id") or tool_key),
                    "invocation_id": (
                        str(payload["invocation_id"])
                        if payload.get("invocation_id")
                        else None
                    ),
                    "tool_name": tool_name,
                    "status": payload.get("status") or (
                        "success" if payload.get("success") is True else "error"
                    ),
                    "success": payload.get("success"),
                    "duration_ms": payload.get("duration_ms"),
                    "error_code": payload.get("error_code"),
                    "error": payload.get("error"),
                    "completed_at": payload.get("ended_at") or occurred_at,
                    **{
                        key: payload[key]
                        for key in ("skill_name", "skill_version")
                        if isinstance(payload.get(key), str)
                    },
                },
            )
    elif event_type == "agent_invocation_started":
        agent_id = payload.get("agent_id") or payload.get("label")
        if agent_id:
            active = set(_as_list(state.get("active_agents")))
            active.add(str(agent_id))
            state["active_agents"] = sorted(active)
        invocation_id = payload.get("invocation_id")
        if invocation_id:
            invocation = {
                "id": str(invocation_id),
                "parent_invocation_id": (
                    str(payload["parent_invocation_id"])
                    if payload.get("parent_invocation_id")
                    else None
                ),
                "node_id": str(payload["node_id"]) if payload.get("node_id") else None,
                "agent_id": str(payload["agent_id"]) if payload.get("agent_id") else None,
                "label": payload.get("label") or payload.get("agent_id") or "Agent",
                "depth": int(payload.get("depth") or 0),
                "status": "running",
                "started_at": payload.get("started_at") or occurred_at,
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "source": payload.get("source"),
                "version": payload.get("version"),
                "session_mode": payload.get("session_mode"),
                "agent_session_id": payload.get("agent_session_id"),
                "context_state": payload.get("context_state"),
                "previous_invocation_count": int(
                    payload.get("previous_invocation_count") or 0
                ),
            }
            state["invocations"] = _upsert_by_key(
                _as_record_list(state.get("invocations")),
                key="id",
                key_value=str(invocation_id),
                update=invocation,
            )
    elif event_type in {
        "agent_invocation_completed",
        "agent_invocation_failed",
        "agent_invocation_cancelled",
    }:
        agent_id = payload.get("agent_id") or payload.get("label")
        if agent_id:
            active = set(_as_list(state.get("active_agents")))
            active.discard(str(agent_id))
            state["active_agents"] = sorted(active)
            if event_type == "agent_invocation_completed":
                completed = set(_as_list(state.get("completed_agents")))
                completed.add(str(agent_id))
                state["completed_agents"] = sorted(completed)
            elif event_type == "agent_invocation_cancelled":
                cancelled = set(_as_list(state.get("cancelled_agents")))
                cancelled.add(str(agent_id))
                state["cancelled_agents"] = sorted(cancelled)
        invocation_id = payload.get("invocation_id")
        if invocation_id:
            status = (
                "completed"
                if event_type == "agent_invocation_completed"
                else "cancelled"
                if event_type == "agent_invocation_cancelled"
                else "failed"
            )
            update = {
                "id": str(invocation_id),
                "status": status,
                "completed_at": payload.get("completed_at") or occurred_at,
                "trace_id": payload.get("trace_id"),
                "agent_session_id": payload.get("agent_session_id"),
            }
            if event_type == "agent_invocation_completed":
                update["usage"] = deepcopy(payload.get("usage"))
                update["provider"] = payload.get("provider")
                update["model"] = payload.get("model")
            else:
                update["failure"] = {
                    key: payload.get(key)
                    for key in ("code", "stage", "message", "retryable")
                    if payload.get(key) is not None
                }
            state["invocations"] = _upsert_by_key(
                _as_record_list(state.get("invocations")),
                key="id",
                key_value=str(invocation_id),
                update=update,
            )
    elif event_type in {
        "delegation_started",
        "delegation_completed",
        "delegation_failed",
        "delegation_skipped",
    }:
        delegation_key = _delegation_key(payload)
        if delegation_key:
            delegation_status = {
                "delegation_started": "running",
                "delegation_completed": "completed",
                "delegation_failed": "failed",
                "delegation_skipped": "skipped",
            }[event_type]
            existing = next(
                (
                    item
                    for item in _as_record_list(state.get("delegations"))
                    if str(item.get("id") or "") == delegation_key
                ),
                {},
            )
            delegation = {
                "id": delegation_key,
                "parent_invocation_id": (
                    str(payload["invocation_id"])
                    if payload.get("invocation_id")
                    else existing.get("parent_invocation_id")
                ),
                "target_node_id": (
                    str(payload["target_node_id"])
                    if payload.get("target_node_id")
                    else existing.get("target_node_id")
                ),
                "target": payload.get("target") or existing.get("target"),
                "status": delegation_status,
                "reason": payload.get("reason") or existing.get("reason"),
                "started_at": (
                    occurred_at
                    if event_type == "delegation_started"
                    else existing.get("started_at")
                ),
                "completed_at": (
                    occurred_at
                    if event_type != "delegation_started"
                    else existing.get("completed_at")
                ),
            }
            state["delegations"] = _upsert_by_key(
                _as_record_list(state.get("delegations")),
                key="id",
                key_value=delegation_key,
                update=delegation,
            )
    elif event_type in {"network.route.selected", "route.selected"}:
        state["current_route"] = payload.get("route") or payload.get("target")
    elif event_type == "usage":
        usage = payload.get("usage")
        state["usage"] = deepcopy(usage if isinstance(usage, dict) else payload)
    elif event_type in {"done", "execution_completed"}:
        state["status"] = "completed"
        result = payload.get("result")
        state["result"] = deepcopy(result if isinstance(result, dict) else payload)
        answer = payload.get("answer") or payload.get("output")
        if isinstance(answer, str):
            state["output"] = answer
        if "parsed_output" in payload:
            state["parsed_output"] = deepcopy(payload.get("parsed_output"))
        if "output_parse_error" in payload:
            state["output_parse_error"] = payload.get("output_parse_error")
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []
    elif event_type in {"error", "execution_failed"}:
        state["status"] = "uncertain" if payload.get("uncertain") else "failed"
        state["error"] = {
            key: payload.get(key)
            for key in (
                "code",
                "message",
                "failure_code",
                "trace_id",
                "root_partial_result_available",
                "completed_child_results_available",
                "completed_child_result_count",
            )
            if payload.get(key) is not None
        }
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []
    elif event_type in {"cancelled", "execution_cancelled"}:
        state["status"] = "cancelled"
        answer = payload.get("answer") or payload.get("output")
        if isinstance(answer, str):
            state["output"] = answer
        result = payload.get("result")
        if isinstance(result, dict):
            state["result"] = deepcopy(result)
        elif payload:
            state["result"] = deepcopy(payload)
        state["activity"] = None
        state["active_tools"] = []
        state["active_agents"] = []

    return state


# Temporary private alias for focused migration of existing projection tests.
_public_event = public_event
