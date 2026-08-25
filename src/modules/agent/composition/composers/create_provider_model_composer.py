from modules.agent.application.use_cases import CreateProviderModelUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_provider_model_controller import CreateProviderModelController
from shared.infra.transactional_handler import TransactionalHandler


def create_provider_model_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = CreateProviderModelUseCase(provider_model_repo, credential_repo)
    controller = CreateProviderModelController(use_case)
    return TransactionalHandler(uow, controller.handle)
