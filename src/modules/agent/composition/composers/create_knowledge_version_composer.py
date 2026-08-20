from modules.agent.application.use_cases import CreateKnowledgeVersionUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyAgentRepositoryWithProviderModels
from modules.agent.infra.database.repositories import SQLAlchemyKnowledgeVersionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository
from modules.agent.presentation.controllers.create_knowledge_version_controller import CreateKnowledgeVersionController
from shared.infra.transactional_handler import TransactionalHandler


def create_knowledge_version_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    knowledge_repo = SQLAlchemyKnowledgeVersionRepository(uow)
    vector_repo = SQLAlchemyVectorSnapshotRepository(uow)
    agent_repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    use_case = CreateKnowledgeVersionUseCase(
        knowledge_repo,
        vector_repo,
        agent_repo,
    )
    controller = CreateKnowledgeVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
