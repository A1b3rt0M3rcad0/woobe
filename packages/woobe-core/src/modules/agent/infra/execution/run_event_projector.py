from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.use_cases.execution_event_factory import (
    completed_event,
    fallback_event,
    llm_event,
    tool_event,
)
from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.events import AgentExecutionFailedV1, AgentMessageCreatedV1
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from shared.contracts.run_event_journal import DurableRunEvent
from shared.contracts.run_event_projector import RunEventProjectorPort
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _compat_payload(run: AgentRun, event: DurableRunEvent) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "trace_id": str(run.trace_id),
        "project_id": str(run.project_id),
        "agent_id": str(run.agent_id),
        "session_id": str(run.session_id) if run.session_id else None,
        **dict(event.metadata),
        **dict(event.payload),
        "journal_sequence": event.sequence,
        "storage_version": event.storage_version,
    }


class AgentRunEventProjector(RunEventProjectorPort):
    """Project durable Agent journal facts into PostgreSQL compatibility models.

    MongoDB remains the execution journal. PostgreSQL is updated transactionally as
    an idempotent read model so existing Run/session/outbox consumers keep working
    while Finalization is removed from the execution path.
    """

    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:
        self._transactions = transactions

    async def project(self, events: Sequence[DurableRunEvent]) -> None:
        grouped: dict[UUID, list[DurableRunEvent]] = defaultdict(list)
        for event in events:
            if event.run_kind == "agent":
                grouped[event.run_id].append(event)
        for run_id, run_events in grouped.items():
            await self._project_run(
                run_id,
                sorted(run_events, key=lambda item: item.sequence),
            )

    async def _project_run(
        self,
        run_id: UUID,
        events: list[DurableRunEvent],
    ) -> None:
        async def apply(
            repositories: AgentRuntimeRepositories,
            outbox: OutboxEventWriter,
        ) -> None:
            run = await repositories.runs.get_by_id_for_update(run_id)
            if run is None:
                raise RuntimeError(f"Cannot project journal for missing Agent Run {run_id}")
            if run.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
                raise RuntimeError(
                    f"Cannot project {EVENT_JOURNAL_STORAGE_VERSION} journal onto "
                    f"Agent Run {run_id} with storage_version={run.storage_version}"
                )

            cursor = int(run.journal_projected_sequence or 0)
            pending = [event for event in events if event.sequence > cursor]
            if not pending:
                return

            for event in pending:
                expected = cursor + 1
                if event.sequence != expected:
                    raise RuntimeError(
                        f"Agent Run {run_id} projection gap: expected {expected}, "
                        f"received {event.sequence}"
                    )
                await self._apply_event(repositories, outbox, run, event)
                cursor = event.sequence

            run.journal_projected_sequence = cursor
            await repositories.runs.save(run)

        await self._transactions.run(apply)

    async def _apply_event(
        self,
        repositories: AgentRuntimeRepositories,
        outbox: OutboxEventWriter,
        run: AgentRun,
        event: DurableRunEvent,
    ) -> None:
        payload = _compat_payload(run, event)

        if event.event_type == "model.invocation.completed":
            await outbox.write(llm_event(run.agent_id, payload))
            return
        if event.event_type in {"tool.call.completed", "tool.call.failed"}:
            await outbox.write(tool_event(run.agent_id, payload))
            return
        if event.event_type == "fallback.triggered":
            await outbox.write(fallback_event(run.agent_id, payload))
            return
        if event.event_type == "run.completed":
            await self._project_completed_message(repositories, outbox, run, event)
            run.status = AgentRunStatus.COMPLETED
            run.usage = dict(event.payload.get("usage") or {})
            run.result = dict(event.payload)
            run.output_message_id = _uuid(event.payload.get("message_id"))
            run.completed_at = _datetime(event.payload.get("completed_at")) or _datetime(
                event.occurred_at
            )
            await outbox.write(completed_event(run.agent_id, payload))
            return
        if event.event_type == "run.failed":
            run.status = AgentRunStatus.FAILED
            run.usage = dict(event.payload.get("usage") or {})
            run.result = dict(event.payload)
            run.failure_code = str(event.payload.get("failure_code") or "runtime_error")
            run.failure_detail = str(event.payload.get("error") or "") or None
            run.completed_at = _datetime(event.payload.get("completed_at")) or _datetime(
                event.occurred_at
            )
            await outbox.write(
                AgentExecutionFailedV1.create(
                    agent_id=run.agent_id,
                    session_id=run.session_id or run.id,
                    payload=payload,
                )
            )
            return
        if event.event_type == "run.cancelled":
            run.status = AgentRunStatus.CANCELLED
            run.result = dict(event.payload)
            run.completed_at = _datetime(event.payload.get("completed_at")) or _datetime(
                event.occurred_at
            )
            return
        if event.event_type == "run.uncertain":
            run.status = AgentRunStatus.UNCERTAIN
            run.result = dict(event.payload)
            run.failure_code = str(
                event.payload.get("failure_code") or "runtime_state_uncertain"
            )
            run.failure_detail = str(event.payload.get("error") or "") or None
            run.completed_at = _datetime(event.payload.get("completed_at")) or _datetime(
                event.occurred_at
            )
            return
        if event.event_type == "run.timed_out":
            # AgentRun has no separate timed_out relational status today. Preserve
            # compatibility by projecting timeout as a terminal failure while the
            # journal retains the precise terminal event type.
            run.status = AgentRunStatus.FAILED
            run.result = dict(event.payload)
            run.failure_code = str(
                event.payload.get("failure_code") or "runtime_timeout"
            )
            run.failure_detail = str(
                event.payload.get("error") or "Runtime timed out"
            )
            run.completed_at = _datetime(event.payload.get("completed_at")) or _datetime(
                event.occurred_at
            )

    async def _project_completed_message(
        self,
        repositories: AgentRuntimeRepositories,
        outbox: OutboxEventWriter,
        run: AgentRun,
        event: DurableRunEvent,
    ) -> None:
        message_id = _uuid(event.payload.get("message_id"))
        session_id = _uuid(event.payload.get("session_id")) or run.session_id
        if message_id is None or session_id is None:
            return

        existing = await repositories.messages.get_by_id(message_id)
        if existing is not None:
            return

        session = await repositories.sessions.get_by_id(session_id)
        if session is None:
            raise RuntimeError(
                f"Cannot project Assistant message {message_id}: Session {session_id} is missing"
            )

        usage = event.payload.get("usage") or {}
        tool_calls = event.payload.get("tool_calls") or []
        message = Message(
            id=message_id,
            project_id=run.project_id,
            agent_id=run.agent_id,
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=str(event.payload.get("answer") or ""),
            input_tokens=(
                int(usage["input_tokens"])
                if usage.get("input_tokens") is not None
                else None
            ),
            output_tokens=(
                int(usage["output_tokens"])
                if usage.get("output_tokens") is not None
                else None
            ),
            cost_usd=(
                float(usage["cost_usd"])
                if usage.get("cost_usd") is not None
                else None
            ),
            data={"tool_calls": list(tool_calls)} if tool_calls else None,
        )
        created = await repositories.messages.create(message)
        session.last_message_at = _datetime(event.payload.get("completed_at")) or _datetime(
            event.occurred_at
        )
        await repositories.sessions.update(session)
        await outbox.write(
            AgentMessageCreatedV1.create(
                message_id=created.id,
                session_id=session_id,
                project_id=run.project_id,
                agent_id=run.agent_id,
                role="assistant",
            )
        )
