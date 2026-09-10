from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from shared.contracts.run_event_buffer import RunEventBufferPort
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.runtime.durability import RunDurabilityBarrier
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.runtime.journal_recorder import DurableRunEventRecorder


FlushOutput = Callable[[UUID], Awaitable[None]]


class NetworkJournalTerminalFinalizer:
    """Persist the Network terminal fact without a PostgreSQL bulk finalization."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        buffer: RunEventBufferPort,
        journal: RunEventJournalPort,
        barrier: RunDurabilityBarrier,
        flush_output: FlushOutput | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._buffer = buffer
        self._journal = journal
        self._barrier = barrier
        self._flush_output = flush_output

    async def _execution(self, execution_id: UUID) -> NetworkExecutionModel | None:
        async with self._session_factory() as session:
            return await session.get(NetworkExecutionModel, execution_id)

    async def finalize(
        self,
        *,
        execution_id: UUID,
        version,
        invocation_states: list[dict[str, Any]],
        terminal_status: str,
        output: str | None,
        trace_id: UUID | None,
        failure_code: str | None = None,
        failure_detail: str | None = None,
        failure_message: str | None = None,
        partial_result_available: bool = False,
        uncertain: bool = False,
        streamed_output: bool = False,
    ) -> bool:
        execution = await self._execution(execution_id)
        if execution is None:
            return False
        if execution.storage_version != EVENT_JOURNAL_STORAGE_VERSION:
            raise RuntimeError(
                f"Network execution {execution_id} is not an event-journal Run"
            )

        state = await self._journal.get_state(execution_id)
        if state is not None and state.terminal_sequence is not None:
            return True

        recorder = DurableRunEventRecorder(
            buffer=self._buffer,
            barrier=self._barrier,
            run_id=execution_id,
            run_kind="network",
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
            attempt=max(1, int(execution.attempt or 1)),
        )

        if state is None or state.durable_sequence == 0:
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
                },
                durable=True,
            )

        if self._flush_output is not None:
            await self._flush_output(execution_id)

        if terminal_status == "completed":
            event_type = "run.completed"
        elif terminal_status == "cancelled":
            event_type = "run.cancelled"
        elif uncertain or terminal_status == "uncertain":
            event_type = "run.uncertain"
        elif failure_code == "network_timeout_exceeded" or terminal_status == "timed_out":
            event_type = "run.timed_out"
        else:
            event_type = "run.failed"

        completed_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "run_id": str(execution_id),
            "project_id": str(execution.project_id),
            "network_id": str(execution.network_id),
            "network_session_id": str(execution.network_session_id),
            "network_version_id": (
                str(execution.network_version_id)
                if execution.network_version_id is not None
                else None
            ),
            "network_version": getattr(version, "version", None) if version else None,
            "output": output or "",
            "trace_id": str(trace_id) if trace_id is not None else None,
            "failure_code": failure_code,
            "failure_detail": failure_detail,
            "failure_message": failure_message,
            "partial": bool(output) and terminal_status != "completed",
            "partial_result_available": bool(partial_result_available or output),
            "uncertain": bool(uncertain or terminal_status == "uncertain"),
            "streamed_output": bool(streamed_output),
            "invocation_count": len(invocation_states),
            "completed_at": completed_at,
        }
        await recorder.emit(event_type, payload, durable=True)
        return True


class NetworkRunPersistenceFinalizer:
    """Select Network terminal persistence from the Run's accepted storage version."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        legacy: NetworkRuntimeFinalizer,
        event_journal: NetworkJournalTerminalFinalizer | None,
    ) -> None:
        self._session_factory = session_factory
        self._legacy = legacy
        self._event_journal = event_journal

    async def _storage_version(self, execution_id: UUID) -> str | None:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            return execution.storage_version if execution is not None else None

    async def finalize(self, **kwargs: Any) -> bool:
        execution_id = UUID(str(kwargs["execution_id"]))
        storage_version = await self._storage_version(execution_id)
        if storage_version == EVENT_JOURNAL_STORAGE_VERSION:
            if self._event_journal is None:
                raise RuntimeError(
                    "event_journal Network Run is missing durable journal dependencies"
                )
            return await self._event_journal.finalize(**kwargs)
        return await self._legacy.finalize(**kwargs)
