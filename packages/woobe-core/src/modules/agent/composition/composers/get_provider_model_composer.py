from modules.agent.application.use_cases import GetProviderModelUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_provider_model_controller import GetProviderModelController
from shared.infra.transactional_handler import TransactionalHandler


def get_provider_model_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = GetProviderModelUseCase(provider_model_repo, credential_repo)
    controller = GetProviderModelController(use_case)
    return TransactionalHandler(uow, controller.handle)
