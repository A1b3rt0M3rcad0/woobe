from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import ListProviderCredentialsUseCase
from modules.agent.presentation.controllers.list_provider_credentials_controller import ListProviderCredentialsController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_provider_credentials_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.provider_credentials
    use_case = ListProviderCredentialsUseCase(repo)
    controller = ListProviderCredentialsController(use_case)
    return TransactionalHandler(uow, controller.handle)
