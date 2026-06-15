from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.create_knowledge_version_controller import CreateKnowledgeVersionController
from modules.agent.application.use_cases import CreateKnowledgeVersionUseCase
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_knowledge_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.knowledge_versions
    use_case = CreateKnowledgeVersionUseCase(repo)
    controller = CreateKnowledgeVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
