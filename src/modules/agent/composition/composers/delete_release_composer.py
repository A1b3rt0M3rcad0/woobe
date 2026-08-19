from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import DeleteReleaseUseCase
from modules.agent.presentation.controllers.delete_release_controller import DeleteReleaseController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def delete_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = DeleteReleaseUseCase(uow.releases)
    controller = DeleteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
