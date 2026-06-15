from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import CreateSecretUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.create_secret_controller import CreateSecretController
from shared.infra.transactional_handler import TransactionalHandler


def create_secret_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = CreateSecretUseCase(uow.secrets, uow.outbox)
    controller = CreateSecretController(use_case)
    return TransactionalHandler(uow, controller.handle)
