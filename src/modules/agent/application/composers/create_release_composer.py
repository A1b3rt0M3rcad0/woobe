from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases import CreateReleaseUseCase
from modules.agent.presentation.controllers.create_release_controller import CreateReleaseController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = CreateReleaseUseCase(repo)
    controller = CreateReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
