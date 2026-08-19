from modules.agent.application.use_cases import ListReleasesUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_releases_controller import ListReleasesController
from shared.infra.transactional_handler import TransactionalHandler


def list_releases_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = ListReleasesUseCase(release_repo)
    controller = ListReleasesController(use_case)
    return TransactionalHandler(uow, controller.handle)
