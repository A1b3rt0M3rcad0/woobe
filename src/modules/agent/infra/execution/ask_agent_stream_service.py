from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.domain.run import AgentRunStatus
from modules.agent.domain.runtime_events import AgentExecutionCancelledV1
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.runtime_streaming import (
    RUNTIME_STREAM_HEARTBEAT_SECONDS,
    RuntimeStreamChannel,
    RuntimeStreamEvent,
    current_runtime_stream,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime_reattach import (
    RuntimeEventPublisher,
    RuntimeStreamReader,
    format_sse_frame,
)
from shared.security.redaction import redact_text

DisconnectCheck = Callable[[], Awaitable[bool]]

# Strong references are intentional: closing an observer must not garbage-collect or
# cancel the execution it was watching.
_DETACHED_AGENT_EXECUTIONS: set[asyncio.Task[Any]] = set()
_DETACHED_AGENT_EVENT_PUMPS: set[asyncio.Task[Any]] = set()


def _track(task: asyncio.Task[Any], registry: set[asyncio.Task[Any]]) -> None:
    registry.add(task)
    task.add_done_callback(registry.discard)


class AskAgentStreamService:
    def __init__(
        self,
        use_case: StructuredOutputAskAgentUseCase,
        transactions: AgentRuntimeTransactionRunner,
        state_store: ExecutionStateStore | None = None,
    ) -> None:
        self._use_case = use_case
        self._transactions = transactions
        self._state_store = state_store or EXECUTION_STATE_STORE
        self._publisher = RuntimeEventPublisher(self._state_store)
        self._reader = RuntimeStreamReader(
            self._state_store,
            heartbeat_seconds=RUNTIME_STREAM_HEARTBEAT_SECONDS,
            block_ms=500,
        )

    async def _run_execution(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
    ) -> AskOutput:
        token = current_runtime_stream.set(channel)
        try:
            result = await self._use_case.execute(input_dto)
            await channel.emit("done", **result.model_dump(mode="json"))
            return result
        except asyncio.CancelledError:
            await self._persist_cancelled(channel, input_dto, "cancel_requested")
            await channel.emit("cancelled", reason="cancel_requested")
            raise
        except Exception as exc:
            # The use case owns durable failure finalization. This terminal runtime
            # event is emitted only after execute() has returned with the failure.
            await channel.emit("error", message=redact_text(str(exc)))
            raise
        finally:
            current_runtime_stream.reset(token)

    async def _persist_cancelled(
        self,
        channel: RuntimeStreamChannel,
        input_dto: AskInput,
        reason: str,
    ) -> bool:
        if channel.trace_id is None:
            return False

        project_id = channel.project_id or input_dto.project_id
        agent_id = channel.agent_id or input_dto.agent_id
        session_id = channel.session_id or input_dto.session_id
        run_id = getattr(channel, "run_id", None)
        payload = {
            "run_id": str(run_id) if run_id is not None else None,
            "trace_id": str(channel.trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id) if session_id is not None else None,
            "request_id": str(channel.request_id),
            "reason": reason,
        }
        event = AgentExecutionCancelledV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
        )

        async def persist(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> bool:
            if run_id is not None:
                lock_reader = getattr(
                    repositories.runs,
                    "get_by_id_for_update",
                    repositories.runs.get_by_id,
                )
                run = await lock_reader(run_id)
                if run is None or run.status != AgentRunStatus.RUNNING:
                    return False
                run.status = AgentRunStatus.CANCELLED
                run.failure_code = "cancelled"
                run.failure_detail = reason
                run.result = payload
                run.completed_at = datetime.now(timezone.utc)
                await repositories.runs.save(run)

            await outbox.write(event)
            return True

        persisted = await self._transactions.run(persist)
        if persisted and run_id is not None:
            try:
                await self._state_store.update(
                    run_id,
                    {"status": "cancelled", "phase": "persisted"},
                )
            except Exception:
                pass
        return persisted

    async def _pump_events(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
        execution_task: asyncio.Task[AskOutput],
    ) -> None:
        buffered: list[RuntimeStreamEvent] = []
        terminal_seen = False
        while not terminal_seen:
            run_id = getattr(channel, "run_id", None)
            runtime_ready = False
            if run_id is not None:
                try:
                    runtime_ready = await self._state_store.get(run_id) is not None
                    if runtime_ready and await self._state_store.is_cancel_requested(run_id):
                        if not execution_task.done():
                            execution_task.cancel()
                except Exception:
                    runtime_ready = False

            try:
                event = await asyncio.wait_for(channel.queue.get(), timeout=0.25)
                buffered.append(event)
            except asyncio.TimeoutError:
                event = None

            run_id = getattr(channel, "run_id", None)
            if run_id is not None and not runtime_ready:
                try:
                    runtime_ready = await self._state_store.get(run_id) is not None
                except Exception:
                    runtime_ready = False

            if run_id is not None and runtime_ready and buffered:
                pending, buffered = buffered, []
                for queued in pending:
                    payload = dict(queued.payload)
                    if queued.event_type == "meta" and payload.get("run_id") is None:
                        payload["run_id"] = str(run_id)
                    await self._publisher.publish(
                        run_id,
                        "agent",
                        queued.event_type,
                        payload,
                    )
                    if queued.event_type in {"done", "error", "cancelled"}:
                        terminal_seen = True

            if execution_task.done() and not buffered and terminal_seen:
                return

            if execution_task.done() and not terminal_seen and event is None:
                # _run_execution always attempts to enqueue a terminal event. Give
                # the queue one final scheduling turn before abandoning the pump.
                await asyncio.sleep(0)
                if channel.queue.empty():
                    return

    async def _durable_fallback(self, run_id: UUID) -> dict[str, Any] | None:
        async def read_run(
            repositories: AgentRuntimeRepositories,
            _outbox: OutboxEventWriter,
        ) -> dict[str, Any] | None:
            run = await repositories.runs.get_by_id(run_id)
            if run is None:
                return None
            status = run.status.value if hasattr(run.status, "value") else str(run.status)
            result = run.result if isinstance(run.result, dict) else None
            output = result.get("answer") if result else None
            return {
                "status": status,
                "output": output or "",
                "result": result,
                "usage": run.usage if isinstance(run.usage, dict) else {},
                "trace_id": str(run.trace_id) if run.trace_id else None,
                "project_id": str(run.project_id),
                "agent_id": str(run.agent_id),
                "session_id": str(run.session_id) if run.session_id else None,
                "updated_at": (
                    run.completed_at.isoformat()
                    if run.completed_at is not None
                    else _now_iso()
                ),
            }

        return await self._transactions.read(read_run)

    async def _wait_for_hot_state(
        self,
        run_id: UUID,
        execution_task: asyncio.Task[AskOutput],
        *,
        timeout_seconds: float = 1.0,
    ) -> None:
        """Bridge the small Acceptance -> hot-state initialization window.

        The canonical Run id becomes available immediately after the durable
        Acceptance commit, while Redis initialization intentionally happens after
        credential preparation. Attaching in that interval would incorrectly look
        like a completed durable-only fallback and close the observer. Wait briefly
        for the hot state; on Redis degradation the timeout preserves execution and
        the caller still falls back to the durable Run rather than creating another.
        """
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            try:
                if await self._state_store.get(run_id) is not None:
                    return
            except Exception:
                return
            if execution_task.done():
                return
            await asyncio.sleep(0.01)

    async def attach(
        self,
        run_id: UUID,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        async for frame in self._reader.stream(
            run_id,
            "agent",
            durable_fallback=lambda: self._durable_fallback(run_id),
        ):
            if disconnect_check is not None and await disconnect_check():
                return
            yield format_sse_frame(frame)

    async def stream(
        self,
        input_dto: AskInput,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        channel = RuntimeStreamChannel()
        execution_task = asyncio.create_task(self._run_execution(input_dto, channel))
        _track(execution_task, _DETACHED_AGENT_EXECUTIONS)
        pump_task = asyncio.create_task(
            self._pump_events(input_dto, channel, execution_task)
        )
        _track(pump_task, _DETACHED_AGENT_EVENT_PUMPS)

        # Acceptance creates the canonical Run before external execution. Wait only
        # for that identity, then observe through the shared hot stream. The request
        # no longer owns execution after this point.
        while getattr(channel, "run_id", None) is None:
            if disconnect_check is not None and await disconnect_check():
                return
            if execution_task.done():
                try:
                    await execution_task
                except asyncio.CancelledError:
                    return
                except Exception as exc:
                    yield self._format_early_error(exc)
                    return
            await asyncio.sleep(0.01)

        run_id = getattr(channel, "run_id")
        await self._wait_for_hot_state(run_id, execution_task)
        async for chunk in self.attach(run_id, disconnect_check):
            yield chunk

    @staticmethod
    def _format_early_error(exc: Exception) -> str:
        payload = {"type": "error", "message": redact_text(str(exc))}
        import json

        return f"event: error\ndata: {json.dumps(payload, default=str)}\n\n"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
