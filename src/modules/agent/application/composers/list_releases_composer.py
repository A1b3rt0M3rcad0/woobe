from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases import ListReleasesUseCase
from modules.agent.presentation.controllers.list_releases_controller import ListReleasesController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_releases_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = ListReleasesUseCase(repo)
    controller = ListReleasesController(use_case)
    return TransactionalHandler(uow, controller.handle)
