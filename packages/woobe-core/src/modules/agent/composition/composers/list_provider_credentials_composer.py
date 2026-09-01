from modules.agent.application.use_cases import ListProviderCredentialsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_provider_credentials_controller import ListProviderCredentialsController
from shared.infra.transactional_handler import TransactionalHandler


def list_provider_credentials_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = ListProviderCredentialsUseCase(repo)
    controller = ListProviderCredentialsController(use_case)
    return TransactionalHandler(uow, controller.handle)
