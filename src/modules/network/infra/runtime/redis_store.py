from __future__ import annotations

from typing import Any
from uuid import UUID

import uuid6

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
    NetworkInvocationState,
)
from shared.contracts.execution_state import ExecutionLease, ExecutionStateStore


class RedisNetworkExecutionStore:
    """Operational Network state. PostgreSQL is intentionally absent here."""

    INVOCATION_PREFIX = "invocation:"
    CONTEXT_PREFIX = "agent_session:"

    def __init__(self, state: ExecutionStateStore) -> None:
        self._state = state
        self._invocation_to_execution: dict[UUID, UUID] = {}

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
        state = await self._state.get(execution.id) or {}
        raw_session_id = (
            state.get(f"{self.CONTEXT_PREFIX}{node_id}") if persist_context else None
        )
        session_id = UUID(str(raw_session_id)) if raw_session_id else None
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
        )
        self._invocation_to_execution[invocation.id] = execution.id
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

    async def complete_invocation(
        self,
        invocation_id: UUID,
        *,
        result: AgentInvocationResult,
        persist_context: bool,
    ) -> None:
        execution_id = self._invocation_to_execution.get(invocation_id)
        if execution_id is None:
            return
        invocation = await self._invocation(execution_id, invocation_id)
        if invocation is None:
            return
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
                "tool_calls": result.tool_calls or [],
                "sources": result.sources or [],
                "parsed_output": result.parsed_output,
                "output_parse_error": result.output_parse_error,
            }
        )
        updates: dict[str, Any] = {
            f"{self.INVOCATION_PREFIX}{invocation_id}": invocation
        }
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
        if execution_id is None:
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
                "agent_session_id": (
                    str(agent_session_id)
                    if agent_session_id
                    else invocation.get("agent_session_id")
                ),
            }
        )
        updates: dict[str, Any] = {
            f"{self.INVOCATION_PREFIX}{invocation_id}": invocation
        }
        if agent_session_id and persist_context:
            updates[f"{self.CONTEXT_PREFIX}{invocation['node_id']}"] = str(
                agent_session_id
            )
        await self._state.update(execution_id, updates)

    async def persist_execution_output(
        self,
        execution_id: UUID,
        result: AgentInvocationResult,
    ) -> None:
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

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None:
        event_payload = dict(payload)
        if invocation_id is not None:
            event_payload["invocation_id"] = str(invocation_id)
        await self._state.append_event(execution_id, event_type, event_payload)

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
        await self._state.update(
            execution_id,
            {"status": status, "phase": "persisted"},
        )
        await self._state.expire(execution_id, ttl_seconds=ttl_seconds)
