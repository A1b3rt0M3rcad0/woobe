from modules.agent.application.use_cases.knowledge_release_validator import (
    KnowledgeReleaseValidator,
)
from modules.agent.application.use_cases.verify_imported_agent import (
    VerifyImportedAgentUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
    SQLAlchemyKnowledgeVersionRepository,
)
from modules.agent.infra.database.vector_snapshot_repositories import (
    SQLAlchemyVectorSnapshotRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.verify_imported_agent_controller import (
    VerifyImportedAgentController,
)
from shared.infra.transactional_handler import TransactionalHandler


def verify_imported_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = VerifyImportedAgentUseCase(
        SQLAlchemyAgentRepositoryWithProviderModels(uow),
        SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow),
        SQLAlchemyProviderCredentialRepository(uow),
        KnowledgeReleaseValidator(
            SQLAlchemyKnowledgeVersionRepository(uow),
            SQLAlchemyVectorSnapshotRepository(uow),
        ),
    )
    return TransactionalHandler(uow, VerifyImportedAgentController(use_case).handle)
