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
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.document_repositories import (
    SQLAlchemyGuardedDocumentRepository,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.infra.storage.factory import create_file_storage
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler


def get_collection_overview_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    snapshot_repo = SQLAlchemyVectorSnapshotRepository(uow)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    document_repo = SQLAlchemyGuardedDocumentRepository(uow)
    use_case = GetCollectionOverviewUseCase(
        snapshot_repo=snapshot_repo,
        collection_repo=collection_repo,
        document_repo=document_repo,
    )
    return TransactionalHandler(uow, use_case.execute)


def preview_vector_snapshot_composer(
    database: AgentDatabase,
    settings: Settings,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    document_repo = SQLAlchemyGuardedDocumentRepository(uow)
    storage = create_file_storage(settings)
    use_case = PreviewVectorSnapshotUseCase(
        collection_repo=collection_repo,
        document_repo=document_repo,
        storage=storage,
    )
    return TransactionalHandler(uow, use_case.execute)


def create_vector_snapshot_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    snapshot_repo = SQLAlchemyVectorSnapshotRepository(uow)
    collection_repo = SQLAlchemyDocumentCollectionRepository(uow)
    document_repo = SQLAlchemyGuardedDocumentRepository(uow)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = CreateVectorSnapshotUseCase(
        snapshot_repo=snapshot_repo,
        collection_repo=collection_repo,
        document_repo=document_repo,
        provider_model_repo=provider_model_repo,
        credential_repo=credential_repo,
    )
    return TransactionalHandler(uow, use_case.execute)


def list_vector_snapshots_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    snapshot_repo = SQLAlchemyVectorSnapshotRepository(uow)
    use_case = ListVectorSnapshotsUseCase(snapshot_repo)
    return TransactionalHandler(uow, use_case.execute)


def get_vector_snapshot_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    snapshot_repo = SQLAlchemyVectorSnapshotRepository(uow)
    use_case = GetVectorSnapshotUseCase(snapshot_repo)
    return TransactionalHandler(uow, use_case.execute)
