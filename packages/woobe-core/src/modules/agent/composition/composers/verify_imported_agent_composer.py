from modules.agent.application.use_cases.knowledge_release_validator import (
    KnowledgeReleaseValidator,
)
from modules.agent.application.use_cases.verify_imported_agent import (
    VerifyImportedAgentUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
    SQLAlchemyAgentRepositoryWithProviderModels,
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentToolRepository,
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


def _build_verification_controller(uow, allow_existing) -> TransactionalHandler:
    use_case = VerifyImportedAgentUseCase(
        SQLAlchemyAgentRepositoryWithProviderModels(uow),
        SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow),
        SQLAlchemyProviderCredentialRepository(uow),
        KnowledgeReleaseValidator(
            SQLAlchemyKnowledgeVersionRepository(uow),
            SQLAlchemyVectorSnapshotRepository(uow),
        ),
        models=SQLAlchemyProviderModelRepository(uow),
        tools=SQLAlchemyAgentToolRepository(uow),
        allow_existing=allow_existing,
    )
    return VerifyImportedAgentController(use_case)


def verify_imported_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_verification_controller(uow, False)
    return TransactionalHandler(uow, controller.handle)


def verify_development_agent_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    controller = _build_verification_controller(uow, True)
    return TransactionalHandler(uow, controller.handle)
