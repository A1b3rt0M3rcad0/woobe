from modules.agent.application.use_cases import ListAgentsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_agents_controller import ListAgentsController
from shared.infra.transactional_handler import TransactionalHandler


def list_agents_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    use_case = ListAgentsUseCase(repo)
    controller = ListAgentsController(use_case)
    return TransactionalHandler(uow, controller.handle)
