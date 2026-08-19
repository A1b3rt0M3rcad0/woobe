from __future__ import annotations

from modules.agent.application.use_cases.vector_snapshot_preview_use_case import (
    PreviewVectorSnapshotUseCase,
)
from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    CreateVectorSnapshotUseCase,
    GetCollectionOverviewUseCase,
    GetVectorSnapshotUseCase,
    ListVectorSnapshotsUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.storage.factory import create_file_storage
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def get_collection_overview_composer(session_factory) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = GetCollectionOverviewUseCase(
        snapshot_repo=uow.vector_snapshots,
        collection_repo=uow.document_collections,
        document_repo=uow.documents,
    )
    return TransactionalHandler(uow, use_case.execute)


def preview_vector_snapshot_composer(session_factory) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    storage = create_file_storage(Settings())
    use_case = PreviewVectorSnapshotUseCase(
        collection_repo=uow.document_collections,
        document_repo=uow.documents,
        storage=storage,
    )
    return TransactionalHandler(uow, use_case.execute)


def create_vector_snapshot_composer(session_factory) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = CreateVectorSnapshotUseCase(
        snapshot_repo=uow.vector_snapshots,
        collection_repo=uow.document_collections,
        document_repo=uow.documents,
        provider_model_repo=uow.provider_models,
        credential_repo=uow.provider_credentials,
    )
    return TransactionalHandler(uow, use_case.execute)


def list_vector_snapshots_composer(session_factory) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListVectorSnapshotsUseCase(uow.vector_snapshots)
    return TransactionalHandler(uow, use_case.execute)


def get_vector_snapshot_composer(session_factory) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = GetVectorSnapshotUseCase(uow.vector_snapshots)
    return TransactionalHandler(uow, use_case.execute)
