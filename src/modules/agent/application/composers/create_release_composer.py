from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeCreateReleaseUseCase
from modules.agent.presentation.controllers.create_release_controller import CreateReleaseController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    validator = KnowledgeReleaseValidator(uow.knowledge_versions, uow.vector_snapshots)
    use_case = KnowledgeSafeCreateReleaseUseCase(uow.releases, validator)
    controller = CreateReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
