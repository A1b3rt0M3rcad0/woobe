from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import CreateProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_project_controller import CreateProjectController
from shared.infra.transactional_handler import TransactionalHandler


def create_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = CreateProjectUseCase(uow.projects, uow.outbox)
    controller = CreateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
