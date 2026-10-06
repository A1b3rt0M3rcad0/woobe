from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    CreateVectorSnapshotUseCase,
)
from modules.agent.application.use_cases.verify_imported_vector import (
    VerifyImportedVectorUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
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
from modules.agent.presentation.controllers.imported_vector_controller import (
    ImportedVectorController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_imported_vector_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = CreateVectorSnapshotUseCase(
        snapshot_repo=SQLAlchemyVectorSnapshotRepository(uow),
        collection_repo=SQLAlchemyDocumentCollectionRepository(uow),
        document_repo=SQLAlchemyGuardedDocumentRepository(uow),
        provider_model_repo=SQLAlchemyProviderModelRepository(uow),
        credential_repo=SQLAlchemyProviderCredentialRepository(uow),
    )
    return TransactionalHandler(uow, ImportedVectorController(use_case).handle)


def verify_imported_vector_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = VerifyImportedVectorUseCase(SQLAlchemyVectorSnapshotRepository(uow))
    return TransactionalHandler(
        uow, ImportedVectorController(use_case, verify=True).handle
    )
