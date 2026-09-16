from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.application.runtime import NetworkExecutionSnapshot
from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.contracts.run_event_buffer import RunEventBufferPort
from shared.runtime.durability import RunDurabilityBarrier
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.runtime.journal_recorder import DurableRunEventRecorder


_CANONICAL_EVENT_TYPES = {
    "execution_started": "execution.started",
    "agent_invocation_started": "agent.invocation.started",
    "agent_invocation_completed": "agent.invocation.completed",
    "agent_invocation_failed": "agent.invocation.failed",
    "agent_invocation_cancelled": "agent.invocation.cancelled",
    "delegation_started": "delegation.started",
    "delegation_completed": "delegation.completed",
    "delegation_failed": "delegation.failed",
    "delegation_skipped": "delegation.skipped",
    "tool_call_started": "tool.call.started",
    "tool_call_completed": "tool.call.completed",
    "tool_call_failed": "tool.call.failed",
    "fallback": "fallback.triggered",
    "fallback_triggered": "fallback.triggered",
}


class JournaledRedisNetworkExecutionStore(RedisNetworkExecutionStore):
    """Network hot store that also records canonical execution facts.

    Redis remains the low-latency operational state and SSE source. Only Runs whose
    accepted PostgreSQL row is explicitly marked ``event_journal_v1`` are copied to
    the durable journal ingress. Journal failures are not best-effort: a recovery
    critical fact must reach the reliable Redis buffer or execution stops.
    """

    def __init__(
        self,
        state,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        buffer: RunEventBufferPort,
        barrier: RunDurabilityBarrier,
        output_batch_bytes: int = 16384,
        output_flush_interval_ms: int = 200,
    ) -> None:
        super().__init__(state)
        self._session_factory = session_factory
        self._run_event_buffer = buffer
        self._run_durability_barrier = barrier
        self._output_batch_bytes = max(1024, int(output_batch_bytes))
        self._output_flush_interval_seconds = max(
            0.01,
            int(output_flush_interval_ms) / 1000.0,
        )
        self._recorders: dict[UUID, DurableRunEventRecorder] = {}
        self._output_buffers: dict[UUID, list[str]] = {}
        self._output_buffer_bytes: dict[UUID, int] = {}
        self._output_last_flush: dict[UUID, float] = {}

    async def _execution_model(self, execution_id: UUID) -> NetworkExecutionModel | None:
        async with self._session_factory() as session:
            return await session.get(NetworkExecutionModel, execution_id)

    async def _ensure_recorder(
        self,
        execution: NetworkExecutionSnapshot,
    ) -> tuple[DurableRunEventRecorder | None, NetworkExecutionModel | None]:
        recorder = self._recorders.get(execution.id)
        if recorder is not None:
            return recorder, None

        model = await self._execution_model(execution.id)
        if model is None or model.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            return None, model

        recorder = DurableRunEventRecorder(
            buffer=self._run_event_buffer,
            barrier=self._run_durability_barrier,
            run_id=execution.id,
            run_kind="network",
            session_id=execution.network_session_id,
            metadata={
                "project_id": str(execution.project_id),
                "network_id": str(execution.network_id),
                "network_session_id": str(execution.network_session_id),
                "network_version_id": (
                    str(execution.network_version_id)
                    if execution.network_version_id is not None
                    else None
                ),
                "visibility": "internal",
            },
            attempt=max(1, int(getattr(model, "attempt", 0) or 1)),
        )
        self._recorders[execution.id] = recorder
        self._output_last_flush.setdefault(execution.id, time.monotonic())
        return recorder, model

    async def initialize(
        self,
        execution: NetworkExecutionSnapshot,
        *,
        ttl_seconds: int,
        agent_contexts: dict[str, str | None] | None = None,
    ) -> None:
        existing = await self._state.get(execution.id)
        recorder, model = await self._ensure_recorder(execution)
        if recorder is not None and existing is None:
            await recorder.emit(
                "run.attempt.started",
                {
                    "attempt": recorder.attempt,
                    "input_message": execution.input_message,
                    "network_id": str(execution.network_id),
                    "network_session_id": str(execution.network_session_id),
                    "network_version_id": (
                        str(execution.network_version_id)
                        if execution.network_version_id is not None
                        else None
                    ),
                    "draft_revision": execution.draft_revision,
                    "definition_snapshot": execution.definition_snapshot,
                    "resolved_bindings_snapshot": execution.resolved_bindings_snapshot,
                    "accepted_at": (
                        model.created_at.isoformat()
                        if model is not None and model.created_at is not None
                        else None
                    ),
                },
                durable=True,
            )

        await super().initialize(
            execution,
            ttl_seconds=ttl_seconds,
            agent_contexts=agent_contexts,
        )
        if recorder is not None:
            await self._state.update(
                execution.id,
                {"storage_version": EVENT_JOURNAL_STORAGE_VERSION},
            )

    def _is_root_output_token(self, payload: dict[str, Any]) -> bool:
        return (
            payload.get("depth") in {0, "0", None}
            and payload.get("visibility", "assistant") == "assistant"
            and payload.get("channel", "final") == "final"
            and isinstance(payload.get("content"), str)
        )

    async def _buffer_output_delta(
        self,
        execution_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        recorder = self._recorders.get(execution_id)
        if recorder is None or not self._is_root_output_token(payload):
            return
        content = str(payload.get("content") or "")
        if not content:
            return
        self._output_buffers.setdefault(execution_id, []).append(content)
        self._output_buffer_bytes[execution_id] = (
            self._output_buffer_bytes.get(execution_id, 0)
            + len(content.encode("utf-8"))
        )
        elapsed = time.monotonic() - self._output_last_flush.get(
            execution_id,
            time.monotonic(),
        )
        if (
            self._output_buffer_bytes[execution_id] >= self._output_batch_bytes
            or elapsed >= self._output_flush_interval_seconds
        ):
            await self.flush_durable_output(execution_id)

    async def flush_durable_output(self, execution_id: UUID) -> None:
        recorder = self._recorders.get(execution_id)
        parts = self._output_buffers.get(execution_id) or []
        if recorder is None or not parts:
            return
        content = "".join(parts)
        self._output_buffers[execution_id] = []
        self._output_buffer_bytes[execution_id] = 0
        self._output_last_flush[execution_id] = time.monotonic()
        await recorder.emit(
            "output.delta.batch",
            {
                "content": content,
                "channel": "final",
                "visibility": "assistant",
            },
        )

    async def _checkpoint_completed_invocation(self, execution_id: UUID) -> None:
        recorder = self._recorders.get(execution_id)
        if recorder is None:
            return
        state = await self.snapshot(execution_id)
        completed_ids: list[str] = []
        agent_contexts: dict[str, str] = {}
        for key, value in state.items():
            if key.startswith(self.INVOCATION_PREFIX) and isinstance(value, dict):
                if value.get("status") == "completed" and value.get("id"):
                    completed_ids.append(str(value["id"]))
            elif key.startswith(self.CONTEXT_PREFIX) and value:
                agent_contexts[key.removeprefix(self.CONTEXT_PREFIX)] = str(value)
        await recorder.checkpoint(
            {
                "phase": "network_invocation_boundary",
                "resume_policy": "completed_invocations_only",
                "completed_invocation_ids": sorted(completed_ids),
                "invocation_count": int(state.get("invocation_count") or 0),
                "agent_contexts": agent_contexts,
                "root_result": (
                    dict(state["root_result"])
                    if isinstance(state.get("root_result"), dict)
                    else None
                ),
            },
            durable=True,
        )

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        payload: dict,
        *,
        invocation_id: UUID | None = None,
    ) -> None:
        await super().emit(
            execution_id,
            event_type,
            payload,
            invocation_id=invocation_id,
        )

        recorder = self._recorders.get(execution_id)
        if recorder is None:
            return

        event_payload = dict(payload)
        if invocation_id is not None:
            event_payload["invocation_id"] = str(invocation_id)
            context = await self._event_context(execution_id, invocation_id)
            if context is not None:
                for key in ("parent_invocation_id", "node_id", "agent_id", "depth"):
                    if context.get(key) is not None:
                        event_payload[key] = context[key]

        if event_type == "token":
            await self._buffer_output_delta(execution_id, event_payload)
            return
        if event_type == "token_retract":
            await self.flush_durable_output(execution_id)
            if event_payload.get("depth") in {0, "0", None}:
                await recorder.emit("output.retracted", event_payload)
            return

        canonical_type = _CANONICAL_EVENT_TYPES.get(event_type)
        if canonical_type is None:
            return

        await self.flush_durable_output(execution_id)
        if invocation_id is not None and canonical_type.startswith("agent.invocation."):
            invocation = await self._invocation(execution_id, invocation_id)
            if invocation is not None:
                event_payload["invocation"] = invocation

        metadata = (
            {"invocation_id": str(invocation_id)}
            if invocation_id is not None
            else None
        )
        await recorder.emit(
            canonical_type,
            event_payload,
            metadata=metadata,
        )

        if canonical_type == "agent.invocation.completed":
            await self._checkpoint_completed_invocation(execution_id)

    async def mark_persisted(
        self,
        execution_id: UUID,
        *,
        status: str,
        ttl_seconds: int = 900,
    ) -> None:
        try:
            await super().mark_persisted(
                execution_id,
                status=status,
                ttl_seconds=ttl_seconds,
            )
        finally:
            self._recorders.pop(execution_id, None)
            self._output_buffers.pop(execution_id, None)
            self._output_buffer_bytes.pop(execution_id, None)
            self._output_last_flush.pop(execution_id, None)
