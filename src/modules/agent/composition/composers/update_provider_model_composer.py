from modules.agent.application.use_cases import UpdateProviderModelUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_provider_model_controller import UpdateProviderModelController
from shared.infra.transactional_handler import TransactionalHandler


def update_provider_model_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    provider_model_repo = SQLAlchemyProviderModelRepository(uow)
    credential_repo = SQLAlchemyProviderCredentialRepository(uow)
    use_case = UpdateProviderModelUseCase(provider_model_repo, credential_repo)
    controller = UpdateProviderModelController(use_case)
    return TransactionalHandler(uow, controller.handle)
