from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import AgentExecutionFailedV1
from modules.agent.background_boundary import SQLAlchemyAgentOutboxEventWriter
from modules.agent.background_boundary import AgentRunModel
from modules.agent.background_boundary import AgentUnitOfWork
from shared.contracts.execution_state import ExecutionStateStore

logger = logging.getLogger(__name__)


class AgentRunRecoveryWorker:
    """Close standalone Runs whose execution owner disappeared.

    The worker never attempts arbitrary execution replay. A direct Agent Run that is
    still `running` after the recovery window is only finalized as `uncertain` when
    its hot runtime state is also absent. That preserves PostgreSQL as durable truth
    without inventing either success or failure after an API-process crash.
    """

    def __init__(
        self,
        *,
        async_engine: AsyncEngine,
        state_store: ExecutionStateStore,
        stale_after_seconds: float,
        batch_size: int = 50,
    ) -> None:
        self._engine = async_engine
        self._state_store = state_store
        self._stale_after_seconds = max(60.0, float(stale_after_seconds))
        self._batch_size = max(1, int(batch_size))

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
            await self._mark_uncertain(run_id, cutoff)

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
                "Recovered orphaned standalone Agent Run as uncertain",
                extra={
                    "run_id": str(run.id),
                    "trace_id": str(run.trace_id),
                    "project_id": str(run.project_id),
                },
            )
