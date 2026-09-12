from __future__ import annotations

from uuid import UUID

from modules.network.infra.database.models import NetworkExecutionModel
from modules.network.infra.services.boundary_service import NetworkBoundaryService
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


class JournalAwareNetworkBoundaryService(NetworkBoundaryService):
    """Resolve active Network executions against the durable terminal source of truth.

    PostgreSQL remains the searchable read model for active discovery. In event-journal
    mode its status is projected asynchronously, so a terminal Mongo journal fact must
    win over a stale SQL RUNNING row before the Control Plane decides to reattach.
    """

    def __init__(
        self,
        *args,
        run_event_journal: RunEventJournalPort | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._run_event_journal = run_event_journal

    async def active_execution(
        self,
        *,
        principal: AuthenticatedPrincipal | ProjectApiPrincipal | None,
        network_session_id: UUID | None,
        network_id: UUID | None,
        environment: str | None,
    ) -> NetworkExecutionModel | None:
        execution = await super().active_execution(
            principal=principal,
            network_session_id=network_session_id,
            network_id=network_id,
            environment=environment,
        )
        if execution is None:
            return None
        if (
            self._run_event_journal is None
            or execution.storage_version != EVENT_JOURNAL_STORAGE_VERSION
        ):
            return execution

        journal_state = await self._run_event_journal.get_state(execution.id)
        if journal_state is not None and journal_state.terminal_status in _TERMINAL_STATUSES:
            return None
        return execution


__all__ = ["JournalAwareNetworkBoundaryService"]
