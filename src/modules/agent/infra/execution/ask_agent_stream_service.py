from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone

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
from shared.security.redaction import redact_text

DisconnectCheck = Callable[[], Awaitable[bool]]


class AskAgentStreamService:
    def __init__(
        self,
        use_case: StructuredOutputAskAgentUseCase,
        transactions: AgentRuntimeTransactionRunner,
    ) -> None:
        self._use_case = use_case
        self._transactions = transactions

    async def _run_execution(
        self,
        input_dto: AskInput,
        channel: RuntimeStreamChannel,
    ) -> AskOutput:
        token = current_runtime_stream.set(channel)
        try:
            return await self._use_case.execute(input_dto)
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

        return await self._transactions.run(persist)

    async def _cancelled_or_completed_event(
        self,
        execution_task: asyncio.Task[AskOutput],
        *,
        cancellation_persisted: bool,
        reason: str,
    ) -> RuntimeStreamEvent:
        if cancellation_persisted:
            return RuntimeStreamEvent(
                event_type="cancelled",
                payload={"reason": reason},
            )

        try:
            result = await execution_task
        except asyncio.CancelledError:
            return RuntimeStreamEvent(
                event_type="cancelled",
                payload={"reason": reason},
            )
        except Exception as exc:
            return RuntimeStreamEvent(
                event_type="error",
                payload={"message": redact_text(str(exc))},
            )
        return RuntimeStreamEvent(
            event_type="done",
            payload=result.model_dump(mode="json"),
        )

    async def stream(
        self,
        input_dto: AskInput,
        disconnect_check: DisconnectCheck | None = None,
    ) -> AsyncGenerator[str, None]:
        channel = RuntimeStreamChannel()
        execution_task = asyncio.create_task(self._run_execution(input_dto, channel))
        heartbeat_at = time.monotonic()
        result_sent = False
        try:
            while True:
                if disconnect_check is not None and await disconnect_check():
                    execution_task.cancel()
                    cancellation_persisted = await self._persist_cancelled(
                        channel,
                        input_dto,
                        "client_disconnected",
                    )
                    terminal_event = await self._cancelled_or_completed_event(
                        execution_task,
                        cancellation_persisted=cancellation_persisted,
                        reason="client_disconnected",
                    )
                    yield self._format_event(terminal_event)
                    break

                try:
                    event = await asyncio.wait_for(channel.queue.get(), timeout=0.25)
                    if event.event_type == "meta":
                        run_id = getattr(channel, "run_id", None)
                        if run_id is not None and event.payload.get("run_id") is None:
                            event = RuntimeStreamEvent(
                                event_type=event.event_type,
                                payload={**event.payload, "run_id": str(run_id)},
                            )
                    yield self._format_event(event)
                    if event.event_type in {"done", "error", "cancelled"}:
                        result_sent = True
                except asyncio.TimeoutError:
                    pass

                now = time.monotonic()
                if now - heartbeat_at >= RUNTIME_STREAM_HEARTBEAT_SECONDS:
                    heartbeat_at = now
                    yield self._format_event(
                        RuntimeStreamEvent(
                            event_type="heartbeat",
                            payload={"ts": datetime.now(timezone.utc).isoformat()},
                        )
                    )

                if execution_task.done():
                    if not result_sent:
                        try:
                            result = execution_task.result()
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="done",
                                    payload=result.model_dump(mode="json"),
                                )
                            )
                        except asyncio.CancelledError:
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="cancelled",
                                    payload={"reason": "cancelled"},
                                )
                            )
                        except Exception as exc:
                            yield self._format_event(
                                RuntimeStreamEvent(
                                    event_type="error",
                                    payload={"message": redact_text(str(exc))},
                                )
                            )
                    break
        finally:
            if not execution_task.done():
                execution_task.cancel()
                try:
                    await execution_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

    @staticmethod
    def _format_event(event: RuntimeStreamEvent) -> str:
        payload = {"type": event.event_type, **event.payload}
        return (
            f"event: {event.event_type}\n"
            f"data: {json.dumps(payload, default=str)}\n\n"
        )
