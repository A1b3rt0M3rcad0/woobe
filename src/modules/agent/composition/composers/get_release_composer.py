from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import GetReleaseUseCase
from modules.agent.presentation.controllers.get_release_controller import GetReleaseController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def get_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = GetReleaseUseCase(uow.releases)
    controller = GetReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
