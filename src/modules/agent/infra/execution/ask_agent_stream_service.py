from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.events import AgentMessageCreatedV1
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
from shared.contracts.time import utc_now
from shared.runtime_reattach import (
    RuntimeEventPublisher,
    RuntimeStreamFrame,
    RuntimeStreamReader,
    format_sse_frame,
)
from shared.security.redaction import redact_text

DisconnectCheck = Callable[[], Awaitable[bool]]
logger = logging.getLogger(__name__)

# Strong references are intentional: closing an observer must not garbage-collect or
# cancel the execution it was watching.
_DETACHED_AGENT_EXECUTIONS: set[asyncio.Task[Any]] = set()
_DETACHED_AGENT_EVENT_PUMPS: set[asyncio.Task[Any]] = set()
_INITIAL_OBSERVER_POLL_SECONDS = 0.25
_TERMINAL_STREAM_EVENTS = {"done", "error", "cancelled"}


def _track(task: asyncio.Task[Any], registry: set[asyncio.Task[Any]]) -> None:
    registry.add(task)

    def completed(done: asyncio.Task[Any]) -> None:
        registry.discard(done)
        if done.cancelled():
            return
        try:
            error = done.exception()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Detached Agent runtime task completion could not be inspected")
            return
        # Agent execution errors are already durably finalized and projected into the
        # Run stream. Pump failures are infrastructure defects and must remain visible.
        if error is not None and registry is _DETACHED_AGENT_EVENT_PUMPS:
            logger.error(
                "Detached Agent runtime event pump failed",
                exc_info=(type(error), error, error.__traceback__),
            )

    task.add_done_callback(completed)


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
            persisted = await self._persist_cancelled(
                channel,
                input_dto,
                "cancel_requested",
            )
            if not persisted:
                emitted_durable_terminal = await self._emit_durable_terminal_after_cancel_race(
                    channel
                )
                if not emitted_durable_terminal:
                    await channel.emit(
                        "error",
                        message="Run cancellation could not be durably confirmed",
                    )
                raise

            result = {
                "answer": channel.public_output,
                "partial": bool(channel.public_output),
                "cancelled": True,
                "reason": "cancel_requested",
                "usage": channel.latest_usage,
            }
            await channel.emit(
                "cancelled",
                reason="cancel_requested",
                output=channel.public_output,
                result=result,
                usage=channel.latest_usage,
                partial=bool(channel.public_output),
                persisted=True,
            )
            raise
        except Exception as exc:
            # The use case owns durable failure finalization. This terminal runtime
            # event is emitted only after execute() has returned with the failure.
            await channel.emit("error", message=redact_text(str(exc)))
            raise
        finally:
            current_runtime_stream.reset(token)

    async def _emit_durable_terminal_after_cancel_race(
        self,
        channel: RuntimeStreamChannel,
    ) -> bool:
        run_id = getattr(channel, "run_id", None)
        if run_id is None:
            return False

        durable = await self._durable_fallback(run_id)
        if durable is None:
            return False

        status = str(durable.get("status") or "")
        result = durable.get("result")
        result_payload = dict(result) if isinstance(result, dict) else {}
        output = durable.get("output")
        output_text = output if isinstance(output, str) else ""
        usage = durable.get("usage")
        usage_payload = usage if isinstance(usage, dict) else None

        if status == "completed":
            result_payload.setdefault("answer", output_text)
            if usage_payload is not None:
                result_payload.setdefault("usage", usage_payload)
            await channel.emit("done", **result_payload)
            return True

        if status == "cancelled":
            result_payload.setdefault("answer", output_text)
            result_payload.setdefault("partial", bool(output_text))
            result_payload.setdefault("cancelled", True)
            result_payload.setdefault("reason", "cancel_requested")
            if usage_payload is not None:
                result_payload.setdefault("usage", usage_payload)
            await channel.emit(
                "cancelled",
                reason=result_payload.get("reason", "cancel_requested"),
                output=output_text,
                result=result_payload,
                usage=usage_payload,
                partial=bool(result_payload.get("partial", bool(output_text))),
                persisted=True,
            )
            return True

        if status in {"failed", "timed_out", "uncertain"}:
            message = durable.get("failure_detail")
            await channel.emit(
                "error",
                message=(
                    redact_text(message)
                    if isinstance(message, str) and message
                    else f"Run already reached terminal status: {status}"
                ),
            )
            return True

        return False

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
        partial_output = channel.public_output
        usage = dict(channel.latest_usage or {})
        result = {
            "answer": partial_output,
            "partial": bool(partial_output),
            "cancelled": True,
            "reason": reason,
            "usage": usage or None,
            "trace_id": str(channel.trace_id),
            "session_id": str(session_id) if session_id is not None else None,
        }
        payload = {
            "run_id": str(run_id) if run_id is not None else None,
            "trace_id": str(channel.trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id) if session_id is not None else None,
            "request_id": str(channel.request_id),
            "reason": reason,
            "partial": bool(partial_output),
        }
        event = AgentExecutionCancelledV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
        )
        completed_at = datetime.now(timezone.utc)

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
                run.failure_code = None
                run.failure_detail = None
                run.result = result
                if usage:
                    run.usage = usage
                run.completed_at = completed_at
                await repositories.runs.save(run)

            if session_id is not None and partial_output:
                session = await repositories.sessions.get_by_id(session_id)
                message = Message(
                    project_id=project_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    role=MessageRole.ASSISTANT,
                    content=partial_output,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    cost_usd=usage.get("cost_usd"),
                    data={
                        "cancelled": True,
                        "partial": True,
                        "run_id": str(run_id) if run_id is not None else None,
                        "trace_id": str(channel.trace_id),
                    },
                )
                created = await repositories.messages.create(message)
                session.last_message_at = utc_now()
                await repositories.sessions.update(session)
                await outbox.write(
                    AgentMessageCreatedV1.create(
                        message_id=created.id,
                        session_id=session_id,
                        project_id=project_id,
                        agent_id=agent_id,
                        role="assistant",
                    )
                )

            await outbox.write(event)
            return True

        persisted = await self._transactions.run(persist)
        if persisted and run_id is not None:
            try:
                await self._state_store.update(
                    run_id,
                    {
                        "status": "cancelled",
                        "phase": "persisted",
                        "terminal_result": result,
                        "usage": usage,
                    },
                )
            except Exception:
                pass
        return persisted

    @staticmethod
    def _event_for_run(
        event: RuntimeStreamEvent,
        run_id: UUID | None,
    ) -> RuntimeStreamEvent:
        if run_id is None or event.payload.get("run_id") is not None:
            return event
        return RuntimeStreamEvent(
            event_type=event.event_type,
            payload={**event.payload, "run_id": str(run_id)},
        )

    async def _pump_events(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
        execution_task: asyncio.Task[AskOutput],
    ) -> None:
        del input_dto
        buffered: list[RuntimeStreamEvent] = []
        terminal_seen = False
        while not terminal_seen:
            try:
                event = await asyncio.wait_for(channel.queue.get(), timeout=0.25)
                run_id = getattr(channel, "run_id", None)
                buffered.append(self._event_for_run(event, run_id))
            except asyncio.TimeoutError:
                event = None

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

            if run_id is not None and runtime_ready and buffered:
                pending, buffered = buffered, []
                for queued in pending:
                    queued = self._event_for_run(queued, run_id)
                    await self._publisher.publish(
                        run_id,
                        "agent",
                        queued.event_type,
                        dict(queued.payload),
                    )
                    if queued.event_type in _TERMINAL_STREAM_EVENTS:
                        terminal_seen = True

            if execution_task.done() and not buffered and terminal_seen:
                return

            if execution_task.done() and buffered and not runtime_ready:
                if any(
                    queued.event_type in _TERMINAL_STREAM_EVENTS
                    for queued in buffered
                ):
                    logger.warning(
                        "Standalone hot event persistence unavailable after terminal Run; "
                        "durable Agent Run remains authoritative"
                    )
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
                "failure_detail": run.failure_detail,
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
        initial_observer_queue = channel.subscribe()
        execution_task = asyncio.create_task(self._run_execution(input_dto, channel))
        _track(execution_task, _DETACHED_AGENT_EXECUTIONS)
        pump_task = asyncio.create_task(
            self._pump_events(input_dto, channel, execution_task)
        )
        _track(pump_task, _DETACHED_AGENT_EVENT_PUMPS)

        # POST observes the active channel directly. The persistence pump consumes its
        # own queue and writes the same events to hot state for GET reattach. A slow or
        # batching Redis path therefore cannot delay already-produced tokens.
        last_heartbeat = time.monotonic()
        try:
            while True:
                if disconnect_check is not None and await disconnect_check():
                    return
                try:
                    event = await asyncio.wait_for(
                        initial_observer_queue.get(),
                        timeout=_INITIAL_OBSERVER_POLL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    now = time.monotonic()
                    if now - last_heartbeat >= RUNTIME_STREAM_HEARTBEAT_SECONDS:
                        last_heartbeat = now
                        yield format_sse_frame(
                            RuntimeStreamFrame(
                                "heartbeat",
                                {
                                    "request_id": str(channel.request_id),
                                    "run_id": (
                                        str(getattr(channel, "run_id"))
                                        if getattr(channel, "run_id", None) is not None
                                        else None
                                    ),
                                    "ts": _now_iso(),
                                },
                            )
                        )
                    if execution_task.done() and pump_task.done() and initial_observer_queue.empty():
                        if execution_task.cancelled():
                            return
                        error = execution_task.exception()
                        if error is not None:
                            yield self._format_early_error(error)
                        return
                    continue

                event = self._event_for_run(
                    event,
                    getattr(channel, "run_id", None),
                )
                last_heartbeat = time.monotonic()
                yield format_sse_frame(
                    RuntimeStreamFrame(
                        event.event_type,
                        dict(event.payload),
                    )
                )
                if event.event_type in _TERMINAL_STREAM_EVENTS:
                    return
        finally:
            channel.unsubscribe(initial_observer_queue)

    @staticmethod
    def _format_early_error(exc: Exception) -> str:
        payload = {"type": "error", "message": redact_text(str(exc))}
        import json

        return f"event: error\ndata: {json.dumps(payload, default=str)}\n\n"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
