from modules.agent.application.use_cases import DeleteReleaseUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.delete_release_controller import DeleteReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def delete_release_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = DeleteReleaseUseCase(release_repo)
    controller = DeleteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
