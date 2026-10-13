from __future__ import annotations

import logging
import socket
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import EmbeddingProviderError
from modules.agent.background_boundary import DetachedVectorBuild, BuildVectorSnapshotUseCase
from modules.agent.background_boundary import VECTOR_SNAPSHOT_BUILDING
from modules.agent.background_boundary import LangchainEmbeddingFactory
from modules.agent.background_boundary import AgentUnitOfWork
from modules.agent.background_boundary import VectorSnapshotModel
from modules.agent.background_boundary import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.background_boundary import create_file_storage
from woobe_workers.consumers.agent.vector_snapshot_claims import claim_vector_snapshot_builds
from woobe_workers.settings import WorkerSettings
from shared.contracts.errors import DomainError

logger = logging.getLogger(__name__)


def _safe_build_error(exc: Exception) -> str:
    if isinstance(exc, EmbeddingProviderError):
        return str(exc)
    if isinstance(exc, DomainError):
        return str(exc)
    return "Vector snapshot build failed because of an internal error."


class VectorSnapshotWorker:
    def __init__(self, async_engine: AsyncEngine) -> None:
        self._engine = async_engine
        self._worker_id = f"{socket.gethostname()}:{uuid4()}"

    async def run(self) -> None:
        pending_ids = await claim_vector_snapshot_builds(
            self._engine,
            worker_id=self._worker_id,
            limit=3,
        )

        if not pending_ids:
            return

        settings = WorkerSettings()
        storage = create_file_storage(settings)
        embedding_factory = LangchainEmbeddingFactory()

        for snapshot_id in pending_ids:
            try:
                async with AgentUnitOfWork(self._engine) as lifecycle_uow:
                    lifecycle_snapshots = SQLAlchemyVectorSnapshotRepository(lifecycle_uow)
                    snapshot = await lifecycle_uow.session.scalar(select(VectorSnapshotModel).where(VectorSnapshotModel.id == snapshot_id).with_for_update())
                    if snapshot is None or snapshot.status != VECTOR_SNAPSHOT_BUILDING or snapshot.locked_by != self._worker_id:
                        continue
                    await lifecycle_snapshots.mark_started(
                        snapshot_id,
                        locked_by=self._worker_id,
                    )

                use_case = DetachedVectorBuild(engine=self._engine, worker_id=self._worker_id,
                    storage=storage, embedding_factory=embedding_factory, encryption_key=settings.encryption_key,
                    use_case_factory=BuildVectorSnapshotUseCase)
                await use_case.execute(snapshot_id)
                logger.info("Vector snapshot %s built", snapshot_id)
            except Exception as exc:
                try:
                    async with AgentUnitOfWork(self._engine) as failure_uow:
                        failure_snapshots = SQLAlchemyVectorSnapshotRepository(failure_uow)
                        snapshot = await failure_uow.session.scalar(select(VectorSnapshotModel).where(VectorSnapshotModel.id == snapshot_id).with_for_update())
                        if snapshot is not None and snapshot.status == VECTOR_SNAPSHOT_BUILDING and snapshot.locked_by == self._worker_id:
                            await failure_snapshots.mark_failed(
                                snapshot_id,
                                _safe_build_error(exc),
                            )
                except Exception:
                    logger.warning("Failed to persist terminal state for vector snapshot %s", snapshot_id)
                logger.warning("Vector snapshot %s failed (%s)", snapshot_id, type(exc).__name__)
