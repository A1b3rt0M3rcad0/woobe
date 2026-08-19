from modules.agent.application.use_cases import ListProviderCredentialsUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_provider_credentials_controller import ListProviderCredentialsController
from shared.infra.transactional_handler import TransactionalHandler


def list_provider_credentials_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = ListProviderCredentialsUseCase(repo)
    controller = ListProviderCredentialsController(use_case)
    return TransactionalHandler(uow, controller.handle)
