from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import ListProjectsUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.list_projects_controller import ListProjectsController
from shared.infra.transactional_handler import TransactionalHandler


def list_projects_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = ListProjectsUseCase(uow.projects)
    controller = ListProjectsController(use_case)
    return TransactionalHandler(uow, controller.handle)
