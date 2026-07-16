from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListReleasesUseCase
from modules.agent.presentation.controllers.list_releases_controller import ListReleasesController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_releases_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListReleasesUseCase(uow.releases)
    controller = ListReleasesController(use_case)
    return TransactionalHandler(uow, controller.handle)
