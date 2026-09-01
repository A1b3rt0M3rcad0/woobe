from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_STAGE_QUEUED,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel

STALE_BUILD_AFTER = timedelta(hours=2)


async def claim_vector_snapshot_builds(
    engine: AsyncEngine,
    *,
    worker_id: str,
    limit: int = 3,
) -> list[UUID]:
    now = datetime.now(timezone.utc)
    stale_before = now - STALE_BUILD_AFTER

    async with AgentUnitOfWork(engine) as uow:
        await uow.session.execute(
            update(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
                VectorSnapshotModel.started_at.isnot(None),
                or_(
                    VectorSnapshotModel.locked_at.is_(None),
                    VectorSnapshotModel.locked_at < stale_before,
                ),
            )
            .values(
                started_at=None,
                locked_at=None,
                locked_by=None,
                current_document_id=None,
                build_stage=VECTOR_SNAPSHOT_STAGE_QUEUED,
            )
        )
        await uow.session.execute(
            update(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
                VectorSnapshotModel.started_at.is_(None),
                VectorSnapshotModel.locked_at < stale_before,
            )
            .values(
                locked_at=None,
                locked_by=None,
                current_document_id=None,
                build_stage=VECTOR_SNAPSHOT_STAGE_QUEUED,
            )
        )

        result = await uow.session.execute(
            select(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
                VectorSnapshotModel.started_at.is_(None),
                VectorSnapshotModel.locked_at.is_(None),
            )
            .order_by(VectorSnapshotModel.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = list(result.scalars().all())
        for model in models:
            model.locked_at = now
            model.locked_by = worker_id
        await uow.session.flush()
        return [model.id for model in models]
