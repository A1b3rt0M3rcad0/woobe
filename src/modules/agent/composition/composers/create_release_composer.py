from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeCreateReleaseUseCase
from modules.agent.application.use_cases.session_mode_compatible_release import SessionModeCompatibleCreateReleaseUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentToolRepository,
    SQLAlchemyKnowledgeVersionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository
from modules.agent.presentation.controllers.create_release_controller import CreateReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def create_release_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    knowledge_repo = SQLAlchemyKnowledgeVersionRepository(uow)
    vector_repo = SQLAlchemyVectorSnapshotRepository(uow)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    tool_repo = SQLAlchemyAgentToolRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    validator = KnowledgeReleaseValidator(knowledge_repo, vector_repo)
    release_use_case = KnowledgeSafeCreateReleaseUseCase(release_repo, validator, tool_repo)
    use_case = SessionModeCompatibleCreateReleaseUseCase(release_use_case, agent_repo)
    controller = CreateReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
