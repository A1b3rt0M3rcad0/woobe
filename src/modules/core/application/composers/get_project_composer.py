from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import GetProjectByIdUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.get_project_controller import GetProjectController
from shared.infra.transactional_handler import TransactionalHandler


def get_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = GetProjectByIdUseCase(uow.projects)
    controller = GetProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
