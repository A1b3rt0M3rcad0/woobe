from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases import UpdateProjectUseCase
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.update_project_controller import UpdateProjectController
from shared.infra.transactional_handler import TransactionalHandler


def update_project_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = UpdateProjectUseCase(uow.projects, uow.outbox)
    controller = UpdateProjectController(use_case)
    return TransactionalHandler(uow, controller.handle)
