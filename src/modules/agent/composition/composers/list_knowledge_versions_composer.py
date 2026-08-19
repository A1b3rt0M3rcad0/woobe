from modules.agent.application.use_cases import ListKnowledgeVersionsUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyKnowledgeVersionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_knowledge_versions_controller import ListKnowledgeVersionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_knowledge_versions_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyKnowledgeVersionRepository(uow)
    use_case = ListKnowledgeVersionsUseCase(repo)
    controller = ListKnowledgeVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
