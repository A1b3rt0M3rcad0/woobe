from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import uuid6

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutionSnapshot,
    NetworkInvocationState,
)
from shared.contracts.execution_state import ExecutionLease, ExecutionStateStore
from shared.runtime_reattach import RuntimeEventPublisher

logger = logging.getLogger(__name__)


def _iso_latency_ms(started_at: Any, ended_at: datetime) -> int:
    if not isinstance(started_at, str) or not started_at:
        return 0
    try:
        started = datetime.fromisoformat(started_at)
    except ValueError:
        return 0
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(round((ended_at - started).total_seconds() * 1000), 0)


def _cancelled_call(active: dict[str, Any], completed_at: datetime) -> dict[str, Any]:
    return {
        **active,
        "status": "cancelled",
        "error": None,
        "ended_at": completed_at.isoformat(),
        "occurred_at": completed_at.isoformat(),
        "latency_ms": _iso_latency_ms(active.get("started_at"), completed_at),
        "input_tokens": active.get("input_tokens"),
        "output_tokens": active.get("output_tokens"),
        "total_tokens": active.get("total_tokens"),
        "cost_usd": active.get("cost_usd"),
        "cost_status": active.get("cost_status") or "unknown_tokens",
        "cost_reason": active.get("cost_reason")
        or "Model invocation was cancelled before final provider usage",
        "usage_complete": False,
    }


def _partial_invocation_diagnostics(
    invocation: dict[str, Any],
    *,
    completed_at: datetime,
) -> dict[str, Any]:
    existing = invocation.get("diagnostics")
    diagnostics = dict(existing) if isinstance(existing, dict) else {}
    llm_calls = invocation.get("llm_calls")
    calls = list(llm_calls) if isinstance(llm_calls, list) else []
    tool_calls = invocation.get("tool_calls")
    tools = list(tool_calls) if isinstance(tool_calls, list) else []
    total_ms = _iso_latency_ms(invocation.get("started_at"), completed_at)
    llm_work_ms = sum(int(call.get("latency_ms") or 0) for call in calls)
    tool_work_ms = sum(
        round(float(call.get("duration_ms") or 0))
        for call in tools
        if isinstance(call, dict)
    )
    tool_wall_ms = int(diagnostics.get("tool_wall_latency_ms") or 0)
    other_ms = max(total_ms - llm_work_ms - tool_wall_ms, 0)
    diagnostics.update(
        {
            "schema_version": 5,
            "agent_runtime_latency_ms": total_ms,
            "total_latency_ms": total_ms,
            "prepare_latency_ms": int(diagnostics.get("prepare_latency_ms") or 0),
            "llm_work_latency_ms": llm_work_ms,
            "llm_runtime_latency_ms": llm_work_ms,
            "tool_wall_latency_ms": tool_wall_ms,
            "tool_work_latency_ms": tool_work_ms,
            "tool_call_duration_sum_ms": tool_work_ms,
            "finalization_work_latency_ms": int(
                diagnostics.get("finalization_work_latency_ms") or 0
            ),
            "persistence_latency_ms": int(diagnostics.get("persistence_latency_ms") or 0),
            "other_latency_ms": other_ms,
            "unaccounted_latency_ms": other_ms,
            "orchestration_latency_ms": diagnostics.get("orchestration_latency_ms"),
            "llm_call_count": len(calls),
            "tool_call_count": len(tools),
            "usage_complete": False,
            "cost_status": diagnostics.get("cost_status") or "unknown_tokens",
        }
    )
    return diagnostics


class RedisNetworkExecutionStore:
    """Operational Network state. PostgreSQL is intentionally absent here."""

    INVOCATION_PREFIX = "invocation:"
    CONTEXT_PREFIX = "agent_session:"

    def __init__(self, state: ExecutionStateStore) -> None:
        self._state = state
        self._events = RuntimeEventPublisher(state)
        self._invocation_to_execution: dict[UUID, UUID] = {}
        # Active invocation identity is already known by this worker. Keep only the
        # causal routing fields in memory so token publication does not require a
        # Redis state read for every provider delta.
        self._invocation_event_context: dict[UUID, dict[str, Any]] = {}
        # Exact public root output is kept in the execution owner process. Projection
        # writes remain batched, but cancellation can still finalize the last emitted
        # assistant delta instead of losing up to one checkpoint interval.
        self._partial_output: dict[UUID, str] = {}
        # A provider/library may swallow task cancellation. Once a Network Run has
        # accepted cancellation, stale provider work must not mutate the canonical
        # hot execution state while the worker finalizes the durable CANCELLED fact.
        self._execution_write_fences: set[UUID] = set()

    async def initialize(
        self,
        execution: NetworkExecutionSnapshot,
        *,
        ttl_seconds: int,
        agent_contexts: dict[str, str | None] | None = None,
    ) -> None:
        existing = await self._state.get(execution.id)
        if existing is not None:
            return
        initial: dict[str, Any] = {
            "status": "running",
            "phase": "network_execution",
            "run_kind": "NETWORK",
            "project_id": str(execution.project_id),
            "network_id": str(execution.network_id),
            "network_session_id": str(execution.network_session_id),
            "network_version_id": (
                str(execution.network_version_id)
                if execution.network_version_id
                else None
            ),
            "draft_revision": execution.draft_revision,
            "input_message": execution.input_message,
            "invocation_count": 0,
            "cancel_requested": False,
        }
        for node_id, session_id in (agent_contexts or {}).items():
            initial[f"{self.CONTEXT_PREFIX}{node_id}"] = session_id
        await self._state.create(execution.id, initial, ttl_seconds=ttl_seconds)
        self._partial_output.setdefault(execution.id, "")
        await self.emit(execution.id, "execution_started", {})

    async def acquire_lease(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> ExecutionLease | None:
        return await self._state.acquire_lease(
            execution_id,
            worker_id=worker_id,
            ttl_seconds=ttl_seconds,
        )

    async def renew_lease(
        self,
        execution_id: UUID,
        *,
        worker_id: str,
        ttl_seconds: int,
    ) -> bool:
        return await self._state.renew_lease(
            execution_id,
            worker_id=worker_id,
            ttl_seconds=ttl_seconds,
        )

    async def is_cancel_requested(self, execution_id: UUID) -> bool:
        return await self._state.is_cancel_requested(execution_id)

    async def request_cancel(self, execution_id: UUID) -> None:
        await self._state.request_cancel(execution_id)

    def fence_execution(self, execution_id: UUID) -> None:
        self._execution_write_fences.add(execution_id)

    def release_execution_fence(self, execution_id: UUID) -> None:
        self._execution_write_fences.discard(execution_id)

    def _writes_fenced(self, execution_id: UUID) -> bool:
        return execution_id in self._execution_write_fences

    def _remember_invocation_event_context(
        self,
        invocation: NetworkInvocationState,
    ) -> None:
        self._invocation_event_context[invocation.id] = {
            "execution_id": str(invocation.network_execution_id),
            "parent_invocation_id": (
                str(invocation.parent_invocation_id)
                if invocation.parent_invocation_id
                else None
            ),
            "node_id": str(invocation.node_id),
            "agent_id": str(invocation.agent_id),
            "depth": invocation.depth,
        }

    def _forget_invocation(self, invocation_id: UUID) -> None:
        self._invocation_event_context.pop(invocation_id, None)
        self._invocation_to_execution.pop(invocation_id, None)

    def _forget_execution_invocations(self, execution_id: UUID) -> None:
        for invocation_id, current_execution_id in list(
            self._invocation_to_execution.items()
        ):
            if current_execution_id == execution_id:
                self._forget_invocation(invocation_id)

    @classmethod
    def _completed_node_invocation_count(
        cls,
        state: dict[str, Any],
        *,
        node_id: UUID,
    ) -> int:
        node_text = str(node_id)
        return sum(
            1
            for key, value in state.items()
            if key.startswith(cls.INVOCATION_PREFIX)
            and isinstance(value, dict)
            and str(value.get("node_id") or "") == node_text
            and value.get("status") == "completed"
        )

    async def start_invocation(
        self,
        *,
        execution: NetworkExecutionSnapshot,
        node_id: UUID,
        agent_id: UUID,
        depth: int,
        message: str,
        parent_invocation_id: UUID | None,
        persist_context: bool,
    ) -> NetworkInvocationState:
        if self._writes_fenced(execution.id):
            raise NetworkExecutionCancelled("Network execution was cancelled")
        state = await self._state.get(execution.id) or {}
        raw_session_id = (
            state.get(f"{self.CONTEXT_PREFIX}{node_id}") if persist_context else None
        )
        session_id = UUID(str(raw_session_id)) if raw_session_id else None
        previous_invocation_count = self._completed_node_invocation_count(
            state,
            node_id=node_id,
        )
        context_state = (
            "stateless"
            if not persist_context
            else "reused"
            if session_id is not None
            else "created"
        )
        invocation = NetworkInvocationState(
            id=uuid6.uuid7(),
            network_execution_id=execution.id,
            network_session_id=execution.network_session_id,
            parent_invocation_id=parent_invocation_id,
            node_id=node_id,
            agent_id=agent_id,
            agent_session_id=session_id,
            trace_id=None,
            depth=depth,
            status="running",
            input_message=message,
            context_state=context_state,
            previous_invocation_count=previous_invocation_count,
        )
        self._invocation_to_execution[invocation.id] = execution.id
        self._remember_invocation_event_context(invocation)
        await self._state.update(
            execution.id,
            {
                f"{self.INVOCATION_PREFIX}{invocation.id}": {
                    "id": str(invocation.id),
                    "agent_run_id": str(invocation.id),
                    "node_id": str(node_id),
                    "agent_id": str(agent_id),
                    "depth": depth,
                    "input_message": message,
                    "parent_invocation_id": (
                        str(parent_invocation_id) if parent_invocation_id else None
                    ),
                    "agent_session_id": str(session_id) if session_id else None,
                    "status": "running",
                    "persist_context": persist_context,
                    "context_state": context_state,
                    "previous_invocation_count": previous_invocation_count,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        await self._state.increment(execution.id, "invocation_count")
        return invocation

    async def _invocation(
        self,
        execution_id: UUID,
        invocation_id: UUID,
    ) -> dict[str, Any] | None:
        state = await self._state.get(execution_id) or {}
        value = state.get(f"{self.INVOCATION_PREFIX}{invocation_id}")
        return dict(value) if isinstance(value, dict) else None

    async def _event_context(
        self,
        execution_id: UUID,
        invocation_id: UUID,
    ) -> dict[str, Any] | None:
        cached = self._invocation_event_context.get(invocation_id)
        if cached is not None and cached.get("execution_id") == str(execution_id):
            return cached

        invocation = await self._invocation(execution_id, invocation_id)
        if invocation is None:
            return None
        recovered = {
            "execution_id": str(execution_id),
            "parent_invocation_id": invocation.get("parent_invocation_id"),
            "node_id": invocation.get("node_id"),
            "agent_id": invocation.get("agent_id"),
            "depth": invocation.get("depth"),
        }
        self._invocation_event_context[invocation_id] = recovered
        self._invocation_to_execution.setdefault(invocation_id, execution_id)
        return recovered

    async def complete_invocation(
        self,
        invocation_id: UUID,
        *,
        result: AgentInvocationResult,
        persist_context: bool,
    ) -> None:
        execution_id = self._invocation_to_execution.get(invocation_id)
        if execution_id is None or self._writes_fenced(execution_id):
            return
        invocation = await self._invocation(execution_id, invocation_id)
        if invocation is None:
            return
        diagnostics = getattr(result, "diagnostics", None)
        llm_calls = getattr(result, "llm_calls", None)
        invocation.update(
            {
                "status": "completed",
                "output_message": result.answer,
                "trace_id": str(result.trace_id) if result.trace_id else None,
                "agent_session_id": (
                    str(result.session_id) if result.session_id else None
                ),
                "provider": result.provider,
                "model": result.model,
                "usage": result.usage,
                "diagnostics": diagnostics if isinstance(diagnostics, dict) else None,
                "llm_calls": llm_calls if isinstance(llm_calls, list) else [],
                "tool_calls": result.tool_calls or [],
                "sources": result.sources or [],
                "parsed_output": result.parsed_output,
                "output_parse_error": result.output_parse_error,
                "started_at": (
                    getattr(result, "started_at", None)
                    or invocation.get("started_at")
                ),
                "completed_at": (
                    getattr(result, "completed_at", None)
                    or datetime.now(timezone.utc).isoformat()
                ),
            }
        )
        invocation.pop("active_llm_call", None)
        updates: dict[str, Any] = {
            f"{self.INVOCATION_PREFIX}{invocation_id}": invocation
        }
        # A successful invocation is the only logical commit point for continuity.
        if result.session_id and persist_context:
            updates[f"{self.CONTEXT_PREFIX}{invocation['node_id']}"] = str(
                result.session_id
            )
        await self._state.update(execution_id, updates)

    async def fail_invocation(
        self,
        invocation_id: UUID,
        error: str,
        *,
        trace_id: UUID | None = None,
        agent_session_id: UUID | None = None,
        persist_context: bool = False,
    ) -> None:
        execution_id = self._invocation_to_execution.get(invocation_id)
        if execution_id is None or self._writes_fenced(execution_id):
            return
        invocation = await self._invocation(execution_id, invocation_id)
        if invocation is None:
            return
        invocation.update(
            {
                "status": "failed",
                "error": error[:4000],
                "trace_id": (
                    str(trace_id) if trace_id else invocation.get("trace_id")
                ),
                # Preserve the failed attempt's Session identity as evidence, but do
                # not advance the node's continuity pointer with a failed Session.
                "agent_session_id": (
                    str(agent_session_id)
                    if agent_session_id
                    else invocation.get("agent_session_id")
                ),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        invocation.pop("active_llm_call", None)
        await self._state.update(
            execution_id,
            {f"{self.INVOCATION_PREFIX}{invocation_id}": invocation},
        )

    async def cancel_running_invocations(
        self,
        execution_id: UUID,
        *,
        reason: str = "Network execution was cancelled",
    ) -> None:
        for item in await self.invocations(execution_id):
            if str(item.get("status") or "") != "running":
                continue
            raw_id = item.get("id")
            if not raw_id:
                continue
            invocation_id = UUID(str(raw_id))
            completed_at = datetime.now(timezone.utc)
            active_llm = item.pop("active_llm_call", None)
            calls = item.get("llm_calls")
            llm_calls = list(calls) if isinstance(calls, list) else []
            if isinstance(active_llm, dict):
                active_call_id = active_llm.get("call_id")
                if not active_call_id or not any(
                    call.get("call_id") == active_call_id
                    for call in llm_calls
                    if isinstance(call, dict)
                ):
                    llm_calls.append(_cancelled_call(active_llm, completed_at))
            item["llm_calls"] = llm_calls
            item["status"] = "cancelled"
            item["error"] = None
            item["completed_at"] = completed_at.isoformat()
            item["diagnostics"] = _partial_invocation_diagnostics(
                item,
                completed_at=completed_at,
            )
            if llm_calls:
                last_call = llm_calls[-1]
                if isinstance(last_call, dict):
                    item["provider"] = item.get("provider") or last_call.get("provider")
                    item["model"] = item.get("model") or last_call.get("model")
            item.setdefault(
                "usage",
                {
                    "input_tokens": None,
                    "output_tokens": None,
                    "total_tokens": None,
                    "cost_usd": None,
                },
            )
            item.setdefault("tool_calls", [])
            item.setdefault("sources", [])
            if int(item.get("depth") or 0) == 0:
                partial = await self.partial_output(execution_id)
                if partial:
                    item["output_message"] = partial
            await self._state.update(
                execution_id,
                {f"{self.INVOCATION_PREFIX}{invocation_id}": item},
            )
            self._invocation_to_execution.setdefault(invocation_id, execution_id)
            await self.emit(
                execution_id,
                "agent_invocation_cancelled",
                {
                    "reason": reason,
                    "output": item.get("output_message"),
                    "partial": bool(item.get("output_message")),
                },
                invocation_id=invocation_id,
            )

    async def partial_output(self, execution_id: UUID) -> str:
        captured = self._partial_output.get(execution_id)
        if captured is not None:
            return captured
        state = await self.snapshot(execution_id)
        projection = state.get("runtime_projection")
        if isinstance(projection, dict) and isinstance(projection.get("output"), str):
            return str(projection.get("output") or "")
        return ""

    async def persist_execution_output(
        self,
        execution_id: UUID,
        result: AgentInvocationResult,
    ) -> None:
        if self._writes_fenced(execution_id):
            return
        self._partial_output[execution_id] = result.answer
        await self._state.update(
            execution_id,
            {
                "root_result": {
                    "answer": result.answer,
                    "trace_id": str(result.trace_id) if result.trace_id else None,
                    "parsed_output": result.parsed_output,
                    "output_parse_error": result.output_parse_error,
                }
            },
        )

    def _capture_partial_output(
        self,
        execution_id: UUID,
        event_type: str,
        event_payload: dict[str, Any],
    ) -> None:
        depth = event_payload.get("depth")
        if depth not in {0, "0"}:
            return
        if event_type == "token":
            if (
                event_payload.get("visibility", "assistant") == "assistant"
                and event_payload.get("channel", "final") == "final"
            ):
                content = event_payload.get("content")
                if isinstance(content, str):
                    self._partial_output[execution_id] = (
                        self._partial_output.get(execution_id, "") + content
                    )
        elif event_type == "token_retract":
            size = event_payload.get("content_length")
            if isinstance(size, int) and not isinstance(size, bool) and size > 0:
                current = self._partial_output.get(execution_id, "")
                self._partial_output[execution_id] = (
                    current[:-size] if size < len(current) else ""
                )

    async def _checkpoint_agent_activity(
        self,
        execution_id: UUID,
        invocation_id: UUID,
        event_payload: dict[str, Any],
    ) -> None:
        status = str(event_payload.get("status") or "")
        phase = event_payload.get("phase")
        # A generic activity notification without an invocation phase cannot create
        # model-invocation evidence. Reject it before touching Redis so event-context
        # recovery remains a single read on a cold cache.
        if status in {"generating_answer", "formatting_response", "thinking"} and (
            not isinstance(phase, str) or not phase
        ):
            return

        invocation = await self._invocation(execution_id, invocation_id)
        if invocation is None or invocation.get("status") != "running":
            return
        active = invocation.get("active_llm_call")
        if status in {"generating_answer", "formatting_response", "thinking"}:
            if isinstance(active, dict) and active.get("phase") == phase:
                return
            now = event_payload.get("occurred_at")
            started_at = now if isinstance(now, str) and now else datetime.now(timezone.utc).isoformat()
            invocation["active_llm_call"] = {
                "call_id": str(uuid6.uuid7()),
                "call_index": len(invocation.get("llm_calls") or []) + 1,
                "phase": phase,
                "status": "running",
                "error": None,
                "started_at": started_at,
                "ended_at": None,
                "occurred_at": started_at,
                "latency_ms": 0,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "cost_usd": None,
                "cost_status": "unknown_tokens",
                "cost_reason": "Model invocation is still in progress",
                "usage_complete": False,
                "provider": event_payload.get("provider"),
                "model": event_payload.get("model") or event_payload.get("model_name"),
                "context_snapshot": None,
                "provider_model_id": None,
                "provider_credential_id": None,
                "pricing_id": None,
                "pricing_snapshot": None,
            }
            invocation["provider"] = invocation.get("provider") or event_payload.get("provider")
            invocation["model"] = (
                invocation.get("model")
                or event_payload.get("model")
                or event_payload.get("model_name")
            )
            await self._state.update(
                execution_id,
                {f"{self.INVOCATION_PREFIX}{invocation_id}": invocation},
            )
            return

        if status in {"calling_tool", "processing_tool_result"} and isinstance(active, dict):
            ended_at = datetime.now(timezone.utc)
            completed = {
                **active,
                "status": "success",
                "ended_at": ended_at.isoformat(),
                "occurred_at": ended_at.isoformat(),
                "latency_ms": _iso_latency_ms(active.get("started_at"), ended_at),
                "usage_complete": False,
                "cost_reason": "Provider usage was not available before capability execution",
            }
            calls = invocation.get("llm_calls")
            llm_calls = list(calls) if isinstance(calls, list) else []
            llm_calls.append(completed)
            invocation["llm_calls"] = llm_calls
            invocation.pop("active_llm_call", None)
            await self._state.update(
                execution_id,
                {f"{self.INVOCATION_PREFIX}{invocation_id}": invocation},
            )

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None:
        if self._writes_fenced(execution_id) and event_type != "agent_invocation_cancelled":
            return

        event_payload = dict(payload)
        invocation: dict[str, Any] | None = None
        if invocation_id is not None:
            event_payload["invocation_id"] = str(invocation_id)
            context = await self._event_context(execution_id, invocation_id)
            if context is not None:
                for key in ("parent_invocation_id", "node_id", "agent_id", "depth"):
                    if context.get(key) is not None:
                        event_payload[key] = context[key]

        self._capture_partial_output(execution_id, event_type, event_payload)

        if event_type == "agent_activity" and invocation_id is not None:
            await self._checkpoint_agent_activity(
                execution_id,
                invocation_id,
                event_payload,
            )

        # The structured failure emitted by NetworkExecutor is the canonical
        # classification. Capture it in hot state so the bulk finalizer does not
        # have to reconstruct or replace the Agent failure later.
        if event_type == "agent_invocation_failed" and invocation_id is not None:
            invocation = await self._invocation(execution_id, invocation_id)
            if invocation is not None:
                event_payload["cause_invocation_id"] = (
                    event_payload.get("cause_invocation_id") or str(invocation_id)
                )
                event_payload["cause_node_id"] = (
                    event_payload.get("cause_node_id")
                    or event_payload.get("node_id")
                    or invocation.get("node_id")
                )
                event_payload["cause_agent_id"] = (
                    event_payload.get("cause_agent_id")
                    or event_payload.get("agent_id")
                    or invocation.get("agent_id")
                )
                failure = dict(event_payload)
                failure.setdefault(
                    "internal_detail",
                    invocation.get("error")
                    or failure.get("message")
                    or "Agent invocation failed",
                )
                invocation["failure"] = failure
                if not invocation.get("trace_id") and failure.get("trace_id"):
                    invocation["trace_id"] = failure["trace_id"]
                await self._state.update(
                    execution_id,
                    {f"{self.INVOCATION_PREFIX}{invocation_id}": invocation},
                )

        try:
            await self._events.publish(
                execution_id,
                "network",
                event_type,
                event_payload,
            )
        finally:
            if invocation_id is not None and event_type in {
                "agent_invocation_completed",
                "agent_invocation_failed",
                "agent_invocation_cancelled",
            }:
                self._forget_invocation(invocation_id)

    async def snapshot(self, execution_id: UUID) -> dict[str, Any]:
        return await self._state.get(execution_id) or {}

    async def invocations(self, execution_id: UUID) -> list[dict[str, Any]]:
        state = await self.snapshot(execution_id)
        values = [
            dict(value)
            for key, value in state.items()
            if key.startswith(self.INVOCATION_PREFIX) and isinstance(value, dict)
        ]
        return sorted(
            values,
            key=lambda item: (int(item.get("depth") or 0), str(item.get("id") or "")),
        )

    async def mark_terminal_pending(
        self,
        execution_id: UUID,
        *,
        status: str,
        result: dict[str, Any],
    ) -> None:
        await self._state.update(
            execution_id,
            {
                "status": "terminal_pending_persist",
                "terminal_status": status,
                "terminal_result": result,
            },
        )

    async def mark_persisted(
        self,
        execution_id: UUID,
        *,
        status: str,
        ttl_seconds: int = 900,
    ) -> None:
        """Publish terminal observability only after PostgreSQL finalization returned."""
        try:
            state = await self.snapshot(execution_id)
            await self._state.update(
                execution_id,
                {"status": status, "phase": "persisted"},
            )
            if not state.get("terminal_event_published"):
                terminal = state.get("terminal_result")
                terminal = terminal if isinstance(terminal, dict) else {}
                root_result = state.get("root_result")
                root_result = root_result if isinstance(root_result, dict) else {}
                if status == "completed":
                    event_type = "execution_completed"
                    payload = {
                        "output": terminal.get("output") or root_result.get("answer"),
                        "trace_id": terminal.get("trace_id") or root_result.get("trace_id"),
                        "parsed_output": root_result.get("parsed_output"),
                        "output_parse_error": root_result.get("output_parse_error"),
                    }
                elif status == "cancelled":
                    event_type = "execution_cancelled"
                    output = terminal.get("output") or root_result.get("answer") or ""
                    payload = {
                        "output": output,
                        "trace_id": terminal.get("trace_id") or root_result.get("trace_id"),
                        "partial": bool(output),
                        "cancelled": True,
                        "result": {
                            "answer": output,
                            "partial": bool(output),
                            "cancelled": True,
                        },
                    }
                else:
                    event_type = "execution_failed"
                    output = terminal.get("output") or ""
                    payload = {
                        "failure_code": terminal.get("failure_code"),
                        "message": (
                            terminal.get("failure_message")
                            or "The Network Run failed before producing a complete result."
                        ),
                        "trace_id": terminal.get("trace_id"),
                        "uncertain": status == "uncertain" or bool(terminal.get("uncertain")),
                        "partial_result_available": bool(
                            terminal.get("partial_result_available") or output
                        ),
                        "output": output,
                        "partial": bool(output),
                    }
                await self._events.publish(
                    execution_id,
                    "network",
                    event_type,
                    payload,
                    force_projection=True,
                )
                await self._state.update(
                    execution_id,
                    {"terminal_event_published": True},
                )
            await self._state.expire(execution_id, ttl_seconds=ttl_seconds)
        except Exception as exc:
            # Durable finalization has already happened. A Redis failure here must
            # not rewrite a successful Network Run as failed.
            logger.warning(
                "Network terminal realtime publication degraded execution_id=%s: %s",
                execution_id,
                exc,
            )
        finally:
            self._forget_execution_invocations(execution_id)
            self._partial_output.pop(execution_id, None)
