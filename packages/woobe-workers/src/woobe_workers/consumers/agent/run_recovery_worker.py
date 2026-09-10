from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import AgentExecutionFailedV1
from modules.agent.background_boundary import SQLAlchemyAgentOutboxEventWriter
from modules.agent.background_boundary import AgentRunModel
from modules.agent.background_boundary import AgentUnitOfWork
from shared.contracts.execution_state import ExecutionStateStore
from shared.contracts.run_event_buffer import RunEventBufferPort
from shared.contracts.run_event_journal import (
    DurableRunEvent,
    RunCheckpoint,
    RunEventJournalPort,
    RunJournalState,
)
from shared.runtime.durability import RunDurabilityBarrier
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.runtime.journal_recorder import DurableRunEventRecorder

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _RecoveryRunRecord:
    id: UUID
    storage_version: str
    project_id: UUID
    agent_id: UUID
    session_id: UUID | None
    trace_id: UUID


@dataclass(frozen=True, slots=True)
class _JournalRecoveryDecision:
    action: str
    reason: str | None = None
    checkpoint: RunCheckpoint | None = None
    attempt: int = 1


class AgentRunRecoveryWorker:
    """Reconcile standalone Runs whose execution owner disappeared.

    Legacy Runs keep the previous PostgreSQL-only uncertain behavior. Event-journal
    Runs are classified from their durable Mongo prefix so recovery never guesses an
    external Tool outcome. Actual re-execution is a separate step and only receives
    Runs classified as resumable.
    """

    def __init__(
        self,
        *,
        async_engine: AsyncEngine,
        state_store: ExecutionStateStore,
        stale_after_seconds: float,
        batch_size: int = 50,
        journal: RunEventJournalPort | None = None,
        buffer: RunEventBufferPort | None = None,
        barrier: RunDurabilityBarrier | None = None,
        recovery_lease_seconds: int = 120,
    ) -> None:
        self._engine = async_engine
        self._state_store = state_store
        self._stale_after_seconds = max(60.0, float(stale_after_seconds))
        self._batch_size = max(1, int(batch_size))
        self._journal = journal
        self._buffer = buffer
        self._barrier = barrier
        self._recovery_lease_seconds = max(30, int(recovery_lease_seconds))
        self._worker_id = f"agent-run-recovery-{uuid4()}"

    async def run(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self._stale_after_seconds
        )
        async with AgentUnitOfWork(self._engine).mark_read_only() as uow:
            result = await uow.session.execute(
                select(AgentRunModel.id)
                .where(
                    AgentRunModel.status == "running",
                    AgentRunModel.network_execution_id.is_(None),
                    AgentRunModel.started_at.is_not(None),
                    AgentRunModel.started_at <= cutoff,
                )
                .order_by(AgentRunModel.started_at.asc(), AgentRunModel.id.asc())
                .limit(self._batch_size)
            )
            run_ids = list(result.scalars().all())

        for run_id in run_ids:
            try:
                hot_state = await self._state_store.get(run_id)
            except Exception as exc:
                # Redis degradation is not proof that the execution died. Defer the
                # decision until hot-state availability can be established safely.
                logger.warning(
                    "Agent Run recovery deferred because runtime state is unavailable run_id=%s: %s",
                    run_id,
                    exc,
                )
                continue
            if hot_state is not None:
                continue
            await self._recover_or_close(run_id, cutoff)

    async def _read_run(
        self,
        run_id: UUID,
        cutoff: datetime,
    ) -> _RecoveryRunRecord | None:
        async with AgentUnitOfWork(self._engine).mark_read_only() as uow:
            result = await uow.session.execute(
                select(AgentRunModel).where(AgentRunModel.id == run_id)
            )
            run = result.scalar_one_or_none()
            if (
                run is None
                or run.status != "running"
                or run.network_execution_id is not None
                or run.started_at is None
                or run.started_at > cutoff
            ):
                return None

            # Never leak an ORM instance outside this read UoW. SQLAlchemy expires
            # attributes when the transaction ends; a recovery decision must use a
            # plain immutable snapshot rather than trigger a lazy refresh on a
            # detached AgentRunModel.
            return _RecoveryRunRecord(
                id=run.id,
                storage_version=str(run.storage_version or "legacy_v1"),
                project_id=run.project_id,
                agent_id=run.agent_id,
                session_id=run.session_id,
                trace_id=run.trace_id,
            )

    async def _recover_or_close(self, run_id: UUID, cutoff: datetime) -> None:
        run = await self._read_run(run_id, cutoff)
        if run is None:
            return
        if run.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            await self._mark_uncertain(run_id, cutoff)
            return

        if self._journal is None or self._buffer is None or self._barrier is None:
            logger.error(
                "Event-journal Agent Run recovery is not configured run_id=%s",
                run_id,
            )
            return

        state = await self._journal.get_state(run_id)
        if state is not None and state.terminal_sequence is not None:
            # The journal already proves a terminal outcome. PostgreSQL projection
            # is asynchronous and will converge without inventing another terminal.
            return

        events = (
            await self._journal.list_events(
                run_id,
                through_sequence=state.durable_sequence,
            )
            if state is not None and state.durable_sequence > 0
            else []
        )
        checkpoint = await self._journal.latest_checkpoint(run_id)
        decision = self._classify_journal_prefix(state, events, checkpoint)
        if decision.action == "resumable":
            logger.warning(
                "Agent Run has a safe durable recovery boundary but re-execution is not wired yet",
                extra={
                    "run_id": str(run_id),
                    "checkpoint_sequence": (
                        decision.checkpoint.through_sequence
                        if decision.checkpoint is not None
                        else 0
                    ),
                    "attempt": decision.attempt,
                },
            )
            return
        if decision.action != "uncertain":
            return

        await self._emit_uncertain_journal_terminal(
            run,
            state=state,
            reason=decision.reason or "unsafe_recovery_boundary",
            attempt=decision.attempt,
        )

    @staticmethod
    def _operation_id(event: DurableRunEvent) -> str | None:
        value = event.payload.get("operation_id") or event.payload.get("tool_call_id")
        return str(value) if value not in {None, ""} else None

    @classmethod
    def _classify_journal_prefix(
        cls,
        state: RunJournalState | None,
        events: list[DurableRunEvent],
        checkpoint: RunCheckpoint | None,
    ) -> _JournalRecoveryDecision:
        if state is not None and state.terminal_sequence is not None:
            return _JournalRecoveryDecision(action="terminal")

        attempt = max(
            [
                int(event.metadata.get("attempt") or event.payload.get("attempt") or 1)
                for event in events
            ]
            + ([int(checkpoint.attempt)] if checkpoint is not None else [1])
        )
        started: dict[str, DurableRunEvent] = {}
        known_terminal: dict[str, DurableRunEvent] = {}
        unknown_terminal: list[DurableRunEvent] = []

        for event in events:
            if event.event_type == "tool.call.started":
                operation_id = cls._operation_id(event)
                if operation_id is not None:
                    started[operation_id] = event
                continue
            if event.event_type not in {"tool.call.completed", "tool.call.failed"}:
                continue
            operation_id = cls._operation_id(event)
            if event.payload.get("external_outcome") != "known":
                unknown_terminal.append(event)
                continue
            if operation_id is not None:
                known_terminal[operation_id] = event

        if unknown_terminal:
            event = min(unknown_terminal, key=lambda item: item.sequence)
            return _JournalRecoveryDecision(
                action="uncertain",
                reason=f"tool_external_outcome_unknown:{event.sequence}",
                attempt=attempt,
            )

        for operation_id, start in started.items():
            if operation_id not in known_terminal:
                return _JournalRecoveryDecision(
                    action="uncertain",
                    reason=f"tool_started_without_known_outcome:{start.sequence}",
                    attempt=attempt,
                )

        latest_tool_terminal = max(
            (event.sequence for event in known_terminal.values()),
            default=0,
        )
        checkpoint_sequence = checkpoint.through_sequence if checkpoint is not None else 0
        if latest_tool_terminal > checkpoint_sequence:
            return _JournalRecoveryDecision(
                action="uncertain",
                reason=(
                    "tool_result_without_causal_checkpoint:"
                    f"{latest_tool_terminal}>{checkpoint_sequence}"
                ),
                attempt=attempt,
            )

        return _JournalRecoveryDecision(
            action="resumable",
            checkpoint=checkpoint,
            attempt=attempt,
        )

    async def _emit_uncertain_journal_terminal(
        self,
        run: _RecoveryRunRecord,
        *,
        state: RunJournalState | None,
        reason: str,
        attempt: int,
    ) -> None:
        await self._state_store.create(
            run.id,
            {
                "status": "recovering",
                "phase": "recovery_classification",
                "attempt": attempt,
                "storage_version": EVENT_JOURNAL_STORAGE_VERSION,
            },
            ttl_seconds=self._recovery_lease_seconds,
        )
        lease = await self._state_store.acquire_lease(
            run.id,
            worker_id=self._worker_id,
            ttl_seconds=self._recovery_lease_seconds,
        )
        if lease is None:
            return

        durable_sequence = state.durable_sequence if state is not None else 0
        await self._buffer.ensure_sequence_at_least(run.id, durable_sequence)
        recorder = DurableRunEventRecorder(
            buffer=self._buffer,
            barrier=self._barrier,
            run_id=run.id,
            run_kind="agent",
            metadata={
                "project_id": str(run.project_id),
                "agent_id": str(run.agent_id),
                "session_id": str(run.session_id) if run.session_id else None,
                "trace_id": str(run.trace_id),
                "visibility": "internal",
            },
            attempt=max(1, int(attempt)),
        )
        now = datetime.now(timezone.utc).isoformat()
        await recorder.emit(
            "run.uncertain",
            {
                "run_id": str(run.id),
                "trace_id": str(run.trace_id),
                "project_id": str(run.project_id),
                "agent_id": str(run.agent_id),
                "session_id": str(run.session_id) if run.session_id else None,
                "failure_code": "unsafe_recovery_boundary",
                "error": (
                    "Standalone Agent Run cannot be resumed without risking replay "
                    "of an external Tool side effect."
                ),
                "recovery_reason": reason,
                "uncertain": True,
                "recovered_at": now,
            },
            durable=True,
        )
        await self._state_store.update(
            run.id,
            {"status": "uncertain", "phase": "persisted"},
        )
        await self._state_store.expire(
            run.id,
            ttl_seconds=self._recovery_lease_seconds,
        )

    async def _mark_uncertain(self, run_id: UUID, cutoff: datetime) -> None:
        async with AgentUnitOfWork(self._engine) as uow:
            result = await uow.session.execute(
                select(AgentRunModel)
                .where(AgentRunModel.id == run_id)
                .with_for_update()
            )
            run = result.scalar_one_or_none()
            if (
                run is None
                or run.status != "running"
                or run.network_execution_id is not None
                or run.started_at is None
                or run.started_at > cutoff
            ):
                return

            now = datetime.now(timezone.utc)
            detail = (
                "Standalone Agent Run exceeded the recovery window without active "
                "runtime state; its final execution outcome cannot be proven."
            )
            payload = {
                "run_id": str(run.id),
                "trace_id": str(run.trace_id),
                "project_id": str(run.project_id),
                "agent_id": str(run.agent_id),
                "session_id": str(run.session_id) if run.session_id else None,
                "error": detail,
                "failure_code": "runtime_state_lost",
                "uncertain": True,
                "recovered_at": now.isoformat(),
            }
            run.status = "uncertain"
            run.failure_code = "runtime_state_lost"
            run.failure_detail = detail
            run.result = payload
            run.completed_at = now

            # Use the Run id as the event discriminator so recovery remains
            # idempotent even when many Runs share the same longitudinal Session.
            await SQLAlchemyAgentOutboxEventWriter(uow).write(
                AgentExecutionFailedV1.create(
                    agent_id=run.agent_id,
                    session_id=run.id,
                    payload=payload,
                )
            )
            logger.warning(
                "Recovered orphaned legacy standalone Agent Run as uncertain",
                extra={
                    "run_id": str(run.id),
                    "trace_id": str(run.trace_id),
                    "project_id": str(run.project_id),
                },
            )
