from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.composition.resources import EXECUTION_STATE_STORE
from modules.agent.domain.run import AgentRun
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from shared.contracts.errors import ConflictError, NotFoundError
from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime_reattach import (
    RuntimeStreamFrame,
    RuntimeStreamGapError,
    RuntimeStreamReader,
    format_sse_frame,
)


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


@dataclass(frozen=True, slots=True)
class AgentChatSurfaceRun:
    id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID | None
    agent_release_id: UUID | None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentChatSurfaceRuntime:
    def __init__(
        self,
        *,
        transactions: AgentRuntimeTransactionRunner,
        state_store: ExecutionStateStore,
    ) -> None:
        self._transactions = transactions
        self._state_store = state_store

    @staticmethod
    def _matches(
        run: AgentRun,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> bool:
        return (
            run.project_id == project_id
            and run.agent_id == agent_id
            and run.session_id == session_id
            and run.agent_release_id == agent_release_id
            and run.network_execution_id is None
            and run.environment == "production"
        )

    @staticmethod
    def _summary(run: AgentRun) -> AgentChatSurfaceRun:
        return AgentChatSurfaceRun(
            id=run.id,
            project_id=run.project_id,
            agent_id=run.agent_id,
            session_id=run.session_id,
            agent_release_id=run.agent_release_id,
            status=str(run.status),
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

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

    async def _load(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> AgentRun:
        async def read_run(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.get_by_id(run_id)
            if run is None or not self._matches(
                run,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
            ):
                raise NotFoundError("Agent Run not found")
            return run

        return await self._transactions.read(read_run)

    async def get(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> AgentChatSurfaceRun:
        run = await self._load(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            agent_release_id=agent_release_id,
        )
        return self._summary(run)

    async def find_active(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> AgentChatSurfaceRun | None:
        async def read_active(repositories: AgentRuntimeRepositories, _outbox):
            run = await repositories.runs.get_active_direct_by_session(session_id)
            if run is None:
                return None
            if not self._matches(
                run,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
            ):
                return None
            return self._summary(run)

        return await self._transactions.read(read_active)

    async def cancel(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> AgentChatSurfaceRun:
        run = await self._load(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            agent_release_id=agent_release_id,
        )
        if str(run.status) in _TERMINAL_STATUSES:
            return self._summary(run)

        try:
            state = await self._state_store.get(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run runtime control state is temporarily unavailable; "
                "cancellation was not requested"
            ) from exc
        if state is None:
            latest = await self._load(
                run_id=run_id,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
            )
            if str(latest.status) in _TERMINAL_STATUSES:
                return self._summary(latest)
            raise ConflictError(
                "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
            )

        try:
            await self._state_store.request_cancel(run_id)
        except Exception as exc:
            raise ConflictError(
                "Agent Run cancellation request could not be recorded safely"
            ) from exc

        summary = self._summary(run)
        return AgentChatSurfaceRun(
            id=summary.id,
            project_id=summary.project_id,
            agent_id=summary.agent_id,
            session_id=summary.session_id,
            agent_release_id=summary.agent_release_id,
            status="cancel_requested",
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )

    async def stream(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
        is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[str]:
        await self._load(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            agent_release_id=agent_release_id,
        )
        reader = RuntimeStreamReader(self._state_store)

        async def durable_fallback() -> dict | None:
            latest = await self._load(
                run_id=run_id,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
            )
            return self._durable_state(latest)

        try:
            async for frame in reader.stream(
                run_id,
                "agent",
                durable_fallback=durable_fallback,
            ):
                if is_disconnected is not None and await is_disconnected():
                    return
                yield format_sse_frame(frame)
        except RuntimeStreamGapError:
            latest = await self._load(
                run_id=run_id,
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                agent_release_id=agent_release_id,
            )
            state = self._durable_state(latest)
            state.update(
                {
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "sequence": None,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield format_sse_frame(
                RuntimeStreamFrame("run.state", state, sequence=None)
            )


def build_agent_chat_surface_runtime() -> AgentChatSurfaceRuntime:
    transactions = AgentRuntimeTransactionRunner(
        build_agent_uow,
        build_agent_read_uow,
    )
    return AgentChatSurfaceRuntime(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
    )


__all__ = [
    "AgentChatSurfaceRun",
    "AgentChatSurfaceRuntime",
    "build_agent_chat_surface_runtime",
]
