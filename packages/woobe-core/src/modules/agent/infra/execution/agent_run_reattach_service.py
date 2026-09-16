from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from modules.agent.domain.run import AgentRun
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError
from shared.contracts.execution_state import ExecutionStateStore
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.runtime.contracts import runtime_state_frame
from shared.runtime import (
    RunReference,
    RuntimeFrame,
    RuntimeObserver,
    RuntimeStreamGapError,
    format_sse_frame,
)
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from shared.runtime.journal_projection import journal_runtime_state
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


class AgentRunReattachService:
    """Own Agent Run discovery, authorization and canonical runtime observation.

    Database work is always executed through short Agent UnitOfWork scopes owned by
    AgentRuntimeTransactionRunner. The observer never owns a database session or the
    execution lifecycle it is watching.
    """

    def __init__(
        self,
        *,
        transactions: AgentRuntimeTransactionRunner,
        state_store: ExecutionStateStore,
        journal: RunEventJournalPort | None = None,
    ) -> None:
        self._transactions = transactions
        self._state_store = state_store
        self._journal = journal
        self._observer = RuntimeObserver(state_store)

    @staticmethod
    def _runtime_target(
        principal: ProjectApiPrincipal,
    ) -> tuple[str | None, UUID | None]:
        target_type = principal.target_type
        target_id = principal.target_id
        if target_type is None and principal.agent_id is not None:
            target_type = "agent"
        if target_id is None and principal.agent_id is not None:
            target_id = principal.agent_id
        return target_type, target_id

    async def _authorize_run(
        self,
        repositories: AgentRuntimeRepositories,
        principal: object | None,
        run: AgentRun,
    ) -> None:
        if isinstance(principal, ProjectApiPrincipal):
            if principal.project_id != run.project_id:
                raise AuthorizationError("Runtime key does not belong to this Project")
            if principal.kind == "runtime":
                target_type, target_id = self._runtime_target(principal)
                if target_type != "agent" or target_id != run.agent_id:
                    raise NotFoundError("Agent Run not found")
                if (
                    principal.environment is not None
                    and principal.environment != run.environment
                ):
                    raise NotFoundError("Agent Run not found")
            return

        if isinstance(principal, AuthenticatedPrincipal):
            await repositories.project_access.require_user_access(
                user_id=principal.user_id,
                project_id=run.project_id,
            )
            return

        raise AuthorizationError("Authentication required")

    async def _load_run(
        self,
        run_id: UUID,
        principal: object | None,
    ) -> AgentRun:
        async def read_run(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.get_by_id(run_id)
            if run is None:
                raise NotFoundError("Agent Run not found")
            await self._authorize_run(repositories, principal, run)
            return run

        return await self._transactions.read(read_run)

    @staticmethod
    def _durable_state(run: AgentRun) -> dict:
        result = run.result if isinstance(run.result, dict) else None
        answer = result.get("answer") if result else None
        updated_at = run.completed_at or run.updated_at or run.created_at
        return {
            "status": str(run.status),
            "output": answer or "",
            "result": result,
            "usage": run.usage if isinstance(run.usage, dict) else {},
            "trace_id": str(run.trace_id) if run.trace_id else None,
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id) if run.session_id else None,
            "updated_at": updated_at.isoformat() if updated_at is not None else None,
        }

    async def _durable_runtime_state(self, run: AgentRun) -> dict:
        base = self._durable_state(run)
        replayed = await journal_runtime_state(
            self._journal,
            run.id,
            "agent",
            base_state=base,
        )
        return replayed or base

    async def authorize(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> None:
        await self._load_run(run_id, principal)

    async def active(
        self,
        *,
        session_id: UUID,
        principal: object | None,
    ) -> dict | None:
        async def read_active(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.get_active_direct_by_session(session_id)
            if run is None:
                return None
            await self._authorize_run(repositories, principal, run)
            return run

        run = await self._transactions.read(read_active)
        if run is None:
            return None

        # PostgreSQL is an asynchronously projected read model for event-journal
        # Runs. A durable terminal journal fact wins over a stale SQL RUNNING row,
        # otherwise the Control Plane repeatedly discovers and reattaches the same
        # already-finished Run until the projector catches up.
        if self._journal is not None and run.storage_version == EVENT_JOURNAL_STORAGE_VERSION:
            journal_state = await self._journal.get_state(run.id)
            if journal_state is not None and journal_state.terminal_status in _TERMINAL_STATUSES:
                return None

        return {
            "run_id": str(run.id),
            "status": str(run.status),
            "session_id": str(run.session_id) if run.session_id else None,
            "agent_id": str(run.agent_id),
            "environment": run.environment,
            "created_at": run.created_at,
        }

    async def stream_sse(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> AsyncIterator[str]:
        async def durable_fallback() -> dict | None:
            latest = await self._load_run(run_id, principal)
            return await self._durable_runtime_state(latest)

        try:
            async for frame in self._observer.observe(
                RunReference.agent(run_id),
                durable_fallback=durable_fallback,
            ):
                yield format_sse_frame(frame)
        except RuntimeStreamGapError:
            latest = await self._load_run(run_id, principal)
            state = await self._durable_runtime_state(latest)
            state.update(
                {
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "sequence": state.get("sequence"),
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield format_sse_frame(
                runtime_state_frame(state)
            )

    async def cancel(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> dict:
        run = await self._load_run(run_id, principal)
        if str(run.status) in _TERMINAL_STATUSES:
            return {"run_id": str(run_id), "status": str(run.status)}

        try:
            state = await self._state_store.get(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run runtime control state is temporarily unavailable; "
                "cancellation was not requested"
            ) from exc

        if state is None:
            latest = await self._load_run(run_id, principal)
            durable = await self._durable_runtime_state(latest)
            durable_status = str(durable.get("status") or "")
            if durable_status in _TERMINAL_STATUSES:
                return {"run_id": str(run_id), "status": durable_status}
            raise ConflictError(
                "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
            )

        try:
            await self._state_store.request_cancel(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run cancellation request could not be recorded safely"
            ) from exc
        return {"run_id": str(run_id), "status": "cancel_requested"}

    async def resolve_target_run(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> dict | None:
        async def read_run(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.resolve_direct_runtime_run(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
                preferred_run_id=preferred_run_id,
                created_after=created_after,
            )
            if run is None:
                return None
            return {"run_id": run.id, "status": str(run.status)}

        return await self._transactions.read(read_run)

    async def _load_target_run(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> AgentRun:
        async def read_run(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.resolve_direct_runtime_run(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
                preferred_run_id=run_id,
            )
            if run is None:
                raise NotFoundError("Agent Run not found")
            return run

        return await self._transactions.read(read_run)

    async def durable_target_state(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> dict:
        run = await self._load_target_run(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            agent_release_id=agent_release_id,
        )
        return await self._durable_runtime_state(run)

    async def cancel_target_run(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> dict:
        run = await self._load_target_run(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            agent_release_id=agent_release_id,
        )
        if str(run.status) in _TERMINAL_STATUSES:
            return {"run_id": str(run_id), "status": str(run.status)}
        try:
            state = await self._state_store.get(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run runtime control state is temporarily unavailable; "
                "cancellation was not requested"
            ) from exc
        if state is None:
            durable = await self._durable_runtime_state(run)
            durable_status = str(durable.get("status") or "")
            if durable_status in _TERMINAL_STATUSES:
                return {"run_id": str(run_id), "status": durable_status}
            raise ConflictError(
                "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
            )
        try:
            await self._state_store.request_cancel(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run cancellation request could not be recorded safely"
            ) from exc
        return {"run_id": str(run_id), "status": "cancel_requested"}
