from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeReleaseLifecycleUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyAgentReleaseRepositoryWithProviderModels
from modules.agent.infra.database.release_activation_repository import SQLAlchemyAgentReleaseActivationRepository
from modules.agent.infra.database.repositories import SQLAlchemyKnowledgeVersionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository
from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def promote_release_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    knowledge_repo = SQLAlchemyKnowledgeVersionRepository(uow)
    vector_repo = SQLAlchemyVectorSnapshotRepository(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    activation_repo = SQLAlchemyAgentReleaseActivationRepository(uow)
    validator = KnowledgeReleaseValidator(knowledge_repo, vector_repo)
    use_case = KnowledgeSafeReleaseLifecycleUseCase(
        release_repo,
        validator,
        activation_repo,
        activation_action="reactivate",
    )
    controller = PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
