from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.run_models import AgentRunModel
from shared.contracts.errors import AuthorizationError, ConflictError, NotFoundError
from shared.contracts.execution_state import ExecutionStateStore
from shared.runtime_reattach import (
    RuntimeStreamFrame,
    RuntimeStreamGapError,
    RuntimeStreamReader,
    format_sse_frame,
)
from shared.security.principal import AuthenticatedPrincipal, ProjectApiPrincipal
from shared.security.tenancy import TenantAuthorizer


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


class AgentRunReattachService:
    """Own Agent Run discovery, authorization and hot-stream recovery.

    HTTP is an observer only. This service keeps database/runtime-state access out of
    presentation while preserving the existing public and Control Plane contracts.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        state_store: ExecutionStateStore,
    ) -> None:
        self._session_factory = session_factory
        self._state_store = state_store

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
        session: AsyncSession,
        principal: object | None,
        run: AgentRunModel,
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
            await TenantAuthorizer(session).authorize(
                user_id=principal.user_id,
                path_params={},
                query_params={"project_id": run.project_id},
                body=None,
            )
            return

        raise AuthorizationError("Authentication required")

    async def _load_run(
        self,
        run_id: UUID,
        principal: object | None,
    ) -> AgentRunModel:
        async with self._session_factory() as session:
            run = await session.get(AgentRunModel, run_id)
            if run is None:
                raise NotFoundError("Agent Run not found")
            await self._authorize_run(session, principal, run)
            return run

    @staticmethod
    def _durable_state(run: AgentRunModel) -> dict:
        result = run.result if isinstance(run.result, dict) else None
        answer = result.get("answer") if result else None
        return {
            "status": str(run.status),
            "output": answer or "",
            "result": result,
            "usage": run.usage if isinstance(run.usage, dict) else {},
            "trace_id": str(run.trace_id) if run.trace_id else None,
            "project_id": str(run.project_id),
            "agent_id": str(run.agent_id),
            "session_id": str(run.session_id) if run.session_id else None,
            "updated_at": (
                run.completed_at.isoformat()
                if run.completed_at is not None
                else run.updated_at.isoformat()
            ),
        }

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
        async with self._session_factory() as session:
            run = await session.scalar(
                select(AgentRunModel)
                .where(
                    AgentRunModel.session_id == session_id,
                    AgentRunModel.status == "running",
                    AgentRunModel.network_execution_id.is_(None),
                )
                .order_by(AgentRunModel.created_at.desc(), AgentRunModel.id.desc())
                .limit(1)
            )
            if run is None:
                return None
            await self._authorize_run(session, principal, run)
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
        reader = RuntimeStreamReader(self._state_store)

        async def durable_fallback() -> dict | None:
            latest = await self._load_run(run_id, principal)
            return self._durable_state(latest)

        try:
            async for frame in reader.stream(
                run_id,
                "agent",
                durable_fallback=durable_fallback,
            ):
                yield format_sse_frame(frame)
        except RuntimeStreamGapError:
            latest = await self._load_run(run_id, principal)
            state = self._durable_state(latest)
            state.update(
                {
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "sequence": 0,
                    "realtime_available": False,
                    "degraded_reason": "runtime_event_gap",
                }
            )
            yield format_sse_frame(
                RuntimeStreamFrame("run.state", state, sequence=0)
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

        state = await self._state_store.get(run_id)
        if state is None:
            raise ConflictError(
                "Agent Run has no active runtime state; cancellation cannot be confirmed safely"
            )
        await self._state_store.request_cancel(run_id)
        return {"run_id": str(run_id), "status": "cancel_requested"}
