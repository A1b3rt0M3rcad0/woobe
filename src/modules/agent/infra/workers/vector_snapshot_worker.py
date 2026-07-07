from __future__ import annotations

import logging
import socket
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.application.use_cases.vector_snapshot_use_cases import BuildVectorSnapshotUseCase
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.storage.factory import create_file_storage
from modules.agent.infra.workers.vector_snapshot_claims import claim_vector_snapshot_builds
from shared.infra.config import Settings

logger = logging.getLogger(__name__)


class VectorSnapshotWorker:
    def __init__(self, async_engine: AsyncEngine) -> None:
        self._engine = async_engine
        self._worker_id = f"{socket.gethostname()}:{uuid4()}"

    async def run(self) -> None:
        session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        pending_ids = await claim_vector_snapshot_builds(
            session_factory,
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
                async with AgentUnitOfWork(session_factory) as uow:
                    use_case = BuildVectorSnapshotUseCase(
                        snapshot_repo=uow.vector_snapshots,
                        document_repo=uow.documents,
                        provider_model_repo=uow.provider_models,
                        credential_repo=uow.provider_credentials,
                        storage=storage,
                        embedding_factory=embedding_factory,
                        settings=settings,
                    )
                    await use_case.execute(snapshot_id)
                logger.info("Vector snapshot %s built", snapshot_id)
            except Exception as exc:
                logger.exception("Vector snapshot %s failed: %s", snapshot_id, exc)
