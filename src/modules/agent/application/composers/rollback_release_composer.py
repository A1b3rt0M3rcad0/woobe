from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases import RollbackReleaseUseCase
from modules.agent.presentation.controllers.rollback_release_controller import RollbackReleaseController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def rollback_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = RollbackReleaseUseCase(repo)
    controller = RollbackReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
