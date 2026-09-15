from __future__ import annotations

import asyncio
import logging
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
from shared.runtime import (
    RunKind,
    RunReference,
    RuntimeEventPublisher,
    RuntimeFrame,
    RuntimeObserver,
    format_sse_frame,
)
from shared.security.redaction import redact_text

DisconnectCheck = Callable[[], Awaitable[bool]]
logger = logging.getLogger(__name__)

# Strong references are intentional: closing an observer must not garbage-collect or
# cancel the execution it was watching.
_DETACHED_AGENT_EXECUTIONS: set[asyncio.Task[Any]] = set()
_DETACHED_AGENT_EVENT_PUMPS: set[asyncio.Task[Any]] = set()
_DETACHED_AGENT_CANCEL_WATCHERS: set[asyncio.Task[Any]] = set()
_INITIAL_OBSERVER_POLL_SECONDS = 0.25
_CANCEL_POLL_SECONDS = 0.05
_TERMINAL_STREAM_EVENTS = {"done", "error", "cancelled"}
_AUTHORITATIVE_TERMINALS = {
    "completed",
    "cancelled",
    "failed",
    "timed_out",
    "uncertain",
}
_AUTHORITATIVE_NON_SUCCESS_TERMINALS = _AUTHORITATIVE_TERMINALS - {"completed"}


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
        if error is not None and registry is not _DETACHED_AGENT_EXECUTIONS:
            logger.error(
                "Detached Agent runtime background task failed",
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
        self._observer = RuntimeObserver(
            self._state_store,
            heartbeat_seconds=RUNTIME_STREAM_HEARTBEAT_SECONDS,
            block_ms=500,
            local_poll_seconds=_INITIAL_OBSERVER_POLL_SECONDS,
        )

    async def _run_execution(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
    ) -> AskOutput:
        token = current_runtime_stream.set(channel)
        try:
            result = await self._use_case.execute(input_dto)

            run_id = getattr(channel, "run_id", None)
            if run_id is not None:
                durable = await self._durable_fallback(run_id)
                durable_status = (
                    str(durable.get("status") or "")
                    if durable is not None
                    else ""
                )
                if durable_status in _AUTHORITATIVE_NON_SUCCESS_TERMINALS:
                    await self._emit_durable_terminal_after_race(channel)
                    return result

            await channel.emit("done", **result.model_dump(mode="json"))
            return result
        except asyncio.CancelledError:
            persisted = await self._persist_cancelled(
                channel,
                input_dto,
                "cancel_requested",
            )
            if not persisted:
                emitted_durable_terminal = await self._emit_durable_terminal_after_race(
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
            run_id = getattr(channel, "run_id", None)
            if run_id is not None:
                durable = await self._durable_fallback(run_id)
                durable_status = (
                    str(durable.get("status") or "")
                    if durable is not None
                    else ""
                )
                if durable_status in _AUTHORITATIVE_TERMINALS:
                    await self._emit_durable_terminal_after_race(channel)
                    raise

            await channel.emit("error", message=redact_text(str(exc)))
            raise
        finally:
            current_runtime_stream.reset(token)

    async def _restore_hot_terminal(
        self,
        run_id: UUID,
        *,
        status: str,
        result: dict[str, Any],
        usage: dict[str, Any] | None,
    ) -> None:
        try:
            payload: dict[str, Any] = {
                "status": status,
                "phase": "persisted",
                "terminal_result": result,
            }
            if usage is not None:
                payload["usage"] = usage
            await self._state_store.update(run_id, payload)
            await self._state_store.expire(run_id, ttl_seconds=900)
        except Exception as exc:
            logger.debug("Could not restore authoritative Agent Run hot terminal: %s", exc)

    async def _emit_durable_terminal_after_race(
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
            await self._restore_hot_terminal(
                run_id,
                status=status,
                result=result_payload,
                usage=usage_payload,
            )
            await channel.emit("done", **result_payload)
            return True

        if status == "cancelled":
            result_payload.setdefault("answer", output_text)
            result_payload.setdefault("partial", bool(output_text))
            result_payload.setdefault("cancelled", True)
            result_payload.setdefault("reason", "cancel_requested")
            if usage_payload is not None:
                result_payload.setdefault("usage", usage_payload)
            await self._restore_hot_terminal(
                run_id,
                status=status,
                result=result_payload,
                usage=usage_payload,
            )
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
            if not isinstance(message, str) or not message:
                candidate = result_payload.get("error") or result_payload.get("message")
                message = candidate if isinstance(candidate, str) else None
            await self._restore_hot_terminal(
                run_id,
                status=status,
                result=result_payload,
                usage=usage_payload,
            )
            await channel.emit(
                "error",
                message=(
                    redact_text(message)
                    if isinstance(message, str) and message
                    else f"Run already reached terminal status: {status}"
                ),
                status=status,
                uncertain=status == "uncertain",
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

        from modules.agent.application.interfaces.execution import InstrumentedExecution
        from modules.agent.application.interfaces.execution_context import current_execution
        from modules.agent.infra.execution.agent_run_metrics import build_agent_run_metrics

        project_id = channel.project_id or input_dto.project_id
        agent_id = channel.agent_id or input_dto.agent_id
        session_id = channel.session_id or input_dto.session_id
        run_id = getattr(channel, "run_id", None)
        partial_output = channel.public_output
        completed_at = datetime.now(timezone.utc)
        execution_context = getattr(channel, "execution_context", None)
        if execution_context is None:
            execution_context = current_execution.get()
        execution = getattr(execution_context, "execution", None)

        usage = dict(channel.latest_usage or {})
        diagnostics: dict[str, Any] | None = None
        llm_calls: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        if execution_context is not None and isinstance(execution, InstrumentedExecution):
            snapshot_calls: list[dict[str, Any]] = []
            for raw_call in execution.llm_calls:
                call = dict(raw_call)
                if call.get("status") == "running":
                    started_text = call.get("started_at")
                    latency_ms = int(call.get("latency_ms") or 0)
                    if isinstance(started_text, str):
                        try:
                            started_at = datetime.fromisoformat(started_text)
                            latency_ms = max(
                                latency_ms,
                                round((completed_at - started_at).total_seconds() * 1000),
                            )
                        except (TypeError, ValueError):
                            pass
                    call.update(
                        {
                            "status": "cancelled",
                            "error": None,
                            "ended_at": completed_at.isoformat(),
                            "occurred_at": completed_at.isoformat(),
                            "latency_ms": max(latency_ms, 0),
                            "input_tokens": call.get("input_tokens"),
                            "output_tokens": call.get("output_tokens"),
                            "total_tokens": call.get("total_tokens"),
                            "cost_usd": call.get("cost_usd"),
                            "cost_status": call.get("cost_status") or "unknown_tokens",
                            "cost_reason": call.get("cost_reason")
                            or "Model invocation was cancelled before final provider usage",
                            "usage_complete": False,
                        }
                    )
                snapshot_calls.append(call)

            snapshot_execution = InstrumentedExecution(
                result=None,
                tool_calls=list(execution.tool_calls),
                llm_calls=snapshot_calls,
                timeline=list(execution.timeline),
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=execution.failure_context,
            )
            try:
                metrics = build_agent_run_metrics(
                    context=execution_context,
                    execution=snapshot_execution,
                    binding=object(),
                    fallback_used=False,
                    finalization_work_ms=0,
                    completed_at=completed_at.isoformat(),
                )
                metric_usage = metrics.usage.model_dump(mode="json")
                for key, value in usage.items():
                    if metric_usage.get(key) is None and value is not None:
                        metric_usage[key] = value
                usage = metric_usage
                diagnostics = metrics.diagnostics
                llm_calls = metrics.llm_calls
                tool_calls = [
                    item.model_dump(mode="json")
                    if hasattr(item, "model_dump")
                    else dict(item)
                    if isinstance(item, dict)
                    else {"value": str(item)}
                    for item in snapshot_execution.tool_calls
                ]
            except Exception as exc:
                logger.warning("Could not build cancelled Agent telemetry snapshot: %s", exc)

        result = {
            "answer": partial_output,
            "partial": bool(partial_output),
            "cancelled": True,
            "reason": reason,
            "usage": usage or None,
            "trace_id": str(channel.trace_id),
            "session_id": str(session_id) if session_id is not None else None,
        }
        if diagnostics is not None:
            result["diagnostics"] = diagnostics
            result["llm_calls"] = llm_calls
            result["tool_calls"] = tool_calls
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
        if diagnostics is not None:
            payload["diagnostics"] = diagnostics
        event = AgentExecutionCancelledV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload=payload,
        )

        async def persist(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> bool:
            run = None
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
                if run is not None:
                    run.output_message_id = created.id
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

            if run is not None:
                await repositories.runs.save(run)

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

    async def _watch_cancellation(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
        execution_task: asyncio.Task[AskOutput],
    ) -> None:
        cancellation_persisted = False
        terminal_projected = False
        while not execution_task.done():
            run_id = getattr(channel, "run_id", None)
            if run_id is None:
                await asyncio.sleep(_CANCEL_POLL_SECONDS)
                continue
            try:
                if not await self._state_store.is_cancel_requested(run_id):
                    await asyncio.sleep(_CANCEL_POLL_SECONDS)
                    continue

                if channel.trace_id is None:
                    await asyncio.sleep(_CANCEL_POLL_SECONDS)
                    continue

                if not cancellation_persisted:
                    cancellation_persisted = await self._persist_cancelled(
                        channel,
                        input_dto,
                        "cancel_requested",
                    )

                if cancellation_persisted and not terminal_projected:
                    terminal_projected = await self._emit_durable_terminal_after_race(
                        channel
                    )

                if not execution_task.done():
                    execution_task.cancel()
                    await asyncio.sleep(_CANCEL_POLL_SECONDS)
                continue
            except Exception as exc:
                logger.debug(
                    "Standalone cancellation watcher could not read hot state: %s",
                    exc,
                )
                await asyncio.sleep(_CANCEL_POLL_SECONDS)

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
        async for frame in self._observer.observe(
            RunReference.agent(run_id),
            durable_fallback=lambda: self._durable_fallback(run_id),
            disconnect_check=disconnect_check,
        ):
            yield format_sse_frame(frame)

    async def stream(
        self,
        input_dto: AskInput,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        channel = RuntimeStreamChannel()
        subscription = self._observer.subscribe_local(
            channel,
            run_kind=RunKind.AGENT,
            run_id_resolver=lambda: getattr(channel, "run_id", None),
            heartbeat_data=lambda: {"request_id": str(channel.request_id)},
        )
        execution_task = asyncio.create_task(self._run_execution(input_dto, channel))
        _track(execution_task, _DETACHED_AGENT_EXECUTIONS)
        pump_task = asyncio.create_task(
            self._pump_events(input_dto, channel, execution_task)
        )
        _track(pump_task, _DETACHED_AGENT_EVENT_PUMPS)
        cancellation_task = asyncio.create_task(
            self._watch_cancellation(input_dto, channel, execution_task)
        )
        _track(cancellation_task, _DETACHED_AGENT_CANCEL_WATCHERS)

        def source_done() -> bool:
            return execution_task.done() and pump_task.done()

        def early_error_frame() -> RuntimeFrame | None:
            if execution_task.cancelled():
                return None
            error = execution_task.exception()
            if error is None:
                return None
            return RuntimeFrame("error", {"message": redact_text(str(error))})

        async for frame in subscription.stream(
            disconnect_check=disconnect_check,
            source_done=source_done,
            early_error_frame=early_error_frame,
        ):
            yield format_sse_frame(frame)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()