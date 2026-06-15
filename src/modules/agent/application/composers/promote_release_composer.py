from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases import PromoteReleaseUseCase
from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def promote_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = PromoteReleaseUseCase(repo)
    controller = PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
