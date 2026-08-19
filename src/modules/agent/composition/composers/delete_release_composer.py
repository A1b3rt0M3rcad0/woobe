from modules.agent.application.use_cases import DeleteReleaseUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentReleaseRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.delete_release_controller import DeleteReleaseController
from shared.infra.transactional_handler import TransactionalHandler


def delete_release_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    release_repo = SQLAlchemyAgentReleaseRepositoryWithProviderModels(uow)
    use_case = DeleteReleaseUseCase(release_repo)
    controller = DeleteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
