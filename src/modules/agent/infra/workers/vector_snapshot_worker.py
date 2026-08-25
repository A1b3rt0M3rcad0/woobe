from __future__ import annotations

import logging
import socket
from typing import Any
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.use_cases.vector_snapshot_use_cases import BuildVectorSnapshotUseCase
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_BUILDING
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyDocumentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.infra.storage.factory import create_file_storage
from modules.agent.infra.workers.vector_snapshot_claims import claim_vector_snapshot_builds
from shared.infra.config import Settings
from shared.contracts.errors import DomainError
from shared.contracts.time import utc_now

logger = logging.getLogger(__name__)


class _DurableBuildSnapshotRepository:
    """Keep build progress durable while final snapshot data stays transactional."""

    def __init__(self, delegate: Any, engine: AsyncEngine, worker_id: str) -> None:
        self._delegate = delegate
        self._engine = engine
        self._worker_id = worker_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def mark_started(self, snapshot_id, *, locked_by: str | None = None) -> None:
        del snapshot_id, locked_by

    async def mark_failed(self, snapshot_id, error: str) -> None:
        del snapshot_id, error

    async def update_build_progress(self, snapshot_id, **updates: Any) -> None:
        async with AgentUnitOfWork(self._engine) as progress_uow:
            snapshot_repo = SQLAlchemyVectorSnapshotRepository(progress_uow)
            await snapshot_repo.update_build_progress(snapshot_id, **updates)
            await progress_uow.session.execute(
                update(VectorSnapshotModel)
                .where(
                    VectorSnapshotModel.id == snapshot_id,
                    VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
                )
                .values(
                    locked_at=utc_now(),
                    locked_by=self._worker_id,
                )
            )


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

        settings = Settings()
        storage = create_file_storage(settings)
        embedding_factory = LangchainEmbeddingFactory()

        for snapshot_id in pending_ids:
            try:
                async with AgentUnitOfWork(self._engine) as lifecycle_uow:
                    lifecycle_snapshots = SQLAlchemyVectorSnapshotRepository(lifecycle_uow)
                    snapshot = await lifecycle_snapshots.get_by_id(snapshot_id)
                    if snapshot is None or snapshot.status != VECTOR_SNAPSHOT_BUILDING:
                        continue
                    await lifecycle_snapshots.mark_started(
                        snapshot_id,
                        locked_by=self._worker_id,
                    )

                async with AgentUnitOfWork(self._engine) as build_uow:
                    build_snapshots = SQLAlchemyVectorSnapshotRepository(build_uow)
                    snapshot_repo = _DurableBuildSnapshotRepository(
                        build_snapshots,
                        self._engine,
                        self._worker_id,
                    )
                    use_case = BuildVectorSnapshotUseCase(
                        snapshot_repo=snapshot_repo,
                        document_repo=SQLAlchemyDocumentRepository(build_uow),
                        provider_model_repo=SQLAlchemyProviderModelRepository(build_uow),
                        credential_repo=SQLAlchemyProviderCredentialRepository(build_uow),
                        storage=storage,
                        embedding_factory=embedding_factory,
                        encryption_key=settings.encryption_key,
                    )
                    await use_case.execute(snapshot_id)
                logger.info("Vector snapshot %s built", snapshot_id)
            except Exception as exc:
                try:
                    async with AgentUnitOfWork(self._engine) as failure_uow:
                        failure_snapshots = SQLAlchemyVectorSnapshotRepository(failure_uow)
                        snapshot = await failure_snapshots.get_by_id(snapshot_id)
                        if snapshot is not None and snapshot.status == VECTOR_SNAPSHOT_BUILDING:
                            await failure_snapshots.mark_failed(
                                snapshot_id,
                                _safe_build_error(exc),
                            )
                except Exception:
                    logger.exception(
                        "Failed to persist terminal state for vector snapshot %s",
                        snapshot_id,
                    )
                logger.exception("Vector snapshot %s failed: %s", snapshot_id, exc)
