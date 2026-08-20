from modules.agent.application.use_cases import GetReleaseUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_release_controller import GetReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def get_release_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = GetReleaseUseCase(release_repo)
    controller = GetReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
