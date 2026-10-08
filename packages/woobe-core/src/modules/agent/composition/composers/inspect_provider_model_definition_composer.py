from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.use_cases.inspect_provider_model_definition import (
    InspectProviderModelDefinitionUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.inspect_provider_model_definition_controller import (
    InspectProviderModelDefinitionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def inspect_provider_model_definition_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    models = SQLAlchemyProviderModelRepository(uow)
    credentials = SQLAlchemyProviderCredentialRepository(uow)
    validator = CreateProviderModelUseCase(models, credentials)
    use_case = InspectProviderModelDefinitionUseCase(validator, models)
    controller = InspectProviderModelDefinitionController(use_case)
    return TransactionalHandler(uow, controller.handle)
