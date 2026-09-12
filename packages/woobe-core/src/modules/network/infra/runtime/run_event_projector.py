from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from shared.contracts.run_event_journal import DurableRunEvent, RunEventJournalPort
from shared.contracts.run_event_projector import RunEventProjectorPort
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION, TERMINAL_EVENT_TYPES


class NetworkRunEventProjector(RunEventProjectorPort):
    """Materialize PostgreSQL Network read models from the durable Mongo journal.

    The existing relational finalizer is deliberately reused here as a projection
    implementation. It may still perform one SQL transaction, but it now runs after
    Mongo durability in the persistence worker rather than in the Network executor's
    critical path.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        journal: RunEventJournalPort,
        finalizer: NetworkRuntimeFinalizer,
    ) -> None:
        self._session_factory = session_factory
        self._journal = journal
        self._finalizer = finalizer
        self._loader = NetworkRuntimeLoader(session_factory)

    async def project(self, events: Sequence[DurableRunEvent]) -> None:
        grouped: dict[UUID, list[DurableRunEvent]] = defaultdict(list)
        for event in events:
            if event.run_kind == "network":
                grouped[event.run_id].append(event)
        for run_id, run_events in grouped.items():
            await self._project_run(
                run_id,
                sorted(run_events, key=lambda item: item.sequence),
            )

    async def _execution(self, run_id: UUID) -> NetworkExecutionModel | None:
        async with self._session_factory() as session:
            return await session.get(NetworkExecutionModel, run_id)

    async def _advance_cursor(self, run_id: UUID, through_sequence: int) -> None:
        async with self._session_factory() as session, session.begin():
            execution = await session.get(
                NetworkExecutionModel,
                run_id,
                with_for_update=True,
            )
            if execution is None:
                raise RuntimeError(f"Cannot project missing Network Run {run_id}")
            execution.journal_projected_sequence = max(
                int(execution.journal_projected_sequence or 0),
                through_sequence,
            )

    @staticmethod
    def _invocation_states(events: Sequence[DurableRunEvent]) -> list[dict[str, Any]]:
        states: dict[str, dict[str, Any]] = {}
        for event in events:
            if not event.event_type.startswith("agent.invocation."):
                continue
            raw = event.payload.get("invocation")
            if not isinstance(raw, dict):
                continue
            invocation_id = raw.get("id") or event.payload.get("invocation_id")
            if invocation_id is None:
                continue
            states[str(invocation_id)] = dict(raw)
        return sorted(
            states.values(),
            key=lambda item: (int(item.get("depth") or 0), str(item.get("id") or "")),
        )

    @staticmethod
    def _uuid(value: Any) -> UUID | None:
        if value in {None, ""}:
            return None
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return None

    async def _materialize_terminal(
        self,
        run_id: UUID,
        terminal: DurableRunEvent,
    ) -> None:
        loaded = await self._loader.load(run_id)
        if loaded is None:
            raise RuntimeError(f"Cannot materialize missing Network Run {run_id}")
        history = await self._journal.list_events(
            run_id,
            through_sequence=terminal.sequence,
            limit=10000,
        )
        invocations = self._invocation_states(history)
        precise_status = TERMINAL_EVENT_TYPES.get(terminal.event_type)
        if precise_status is None:
            return
        terminal_status = "failed" if precise_status == "timed_out" else precise_status
        payload = terminal.payload
        await self._finalizer.finalize(
            execution_id=run_id,
            version=loaded.version,
            invocation_states=invocations,
            terminal_status=terminal_status,
            output=str(payload.get("output") or "") or None,
            trace_id=self._uuid(payload.get("trace_id")),
            failure_code=(
                str(payload["failure_code"])
                if payload.get("failure_code") is not None
                else None
            ),
            failure_detail=(
                str(payload["failure_detail"])
                if payload.get("failure_detail") is not None
                else None
            ),
            failure_message=(
                str(payload["failure_message"])
                if payload.get("failure_message") is not None
                else None
            ),
            partial_result_available=bool(payload.get("partial_result_available")),
            uncertain=bool(payload.get("uncertain")),
            streamed_output=bool(payload.get("streamed_output")),
        )

    async def _project_run(
        self,
        run_id: UUID,
        events: list[DurableRunEvent],
    ) -> None:
        execution = await self._execution(run_id)
        if execution is None:
            raise RuntimeError(f"Cannot project missing Network Run {run_id}")
        if execution.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            raise RuntimeError(
                f"Cannot project {EVENT_JOURNAL_STORAGE_VERSION} journal onto "
                f"Network Run {run_id} with storage_version={execution.storage_version}"
            )

        cursor = int(execution.journal_projected_sequence or 0)
        pending = [event for event in events if event.sequence > cursor]
        if not pending:
            return

        expected = cursor + 1
        for event in pending:
            if event.sequence != expected:
                raise RuntimeError(
                    f"Network Run {run_id} projection gap: expected {expected}, "
                    f"received {event.sequence}"
                )
            expected += 1

        terminal = next(
            (
                event
                for event in reversed(pending)
                if event.event_type in TERMINAL_EVENT_TYPES
            ),
            None,
        )
        if terminal is not None:
            await self._materialize_terminal(run_id, terminal)

        await self._advance_cursor(run_id, pending[-1].sequence)
