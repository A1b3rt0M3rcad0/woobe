from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.list_knowledge_versions_controller import ListKnowledgeVersionsController
from modules.agent.application.use_cases import ListKnowledgeVersionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_knowledge_versions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.knowledge_versions
    use_case = ListKnowledgeVersionsUseCase(repo)
    controller = ListKnowledgeVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
