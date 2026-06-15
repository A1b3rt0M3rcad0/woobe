from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.application.use_cases import ListSecretsUseCase
from modules.tools.infra.database.unit_of_work import ToolsUnitOfWork
from modules.tools.presentation.controllers.list_secrets_controller import ListSecretsController
from shared.infra.transactional_handler import TransactionalHandler


def list_secrets_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = ToolsUnitOfWork(session_factory)
    use_case = ListSecretsUseCase(uow.secrets)
    controller = ListSecretsController(use_case)
    return TransactionalHandler(uow, controller.handle)
