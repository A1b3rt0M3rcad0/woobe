from modules.agent.application.use_cases import GetAgentByIdUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyAgentRepositoryWithProviderModels,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_agent_controller import GetAgentController
from shared.infra.transactional_handler import TransactionalHandler


def get_agent_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentRepositoryWithProviderModels(uow)
    use_case = GetAgentByIdUseCase(repo)
    controller = GetAgentController(use_case)
    return TransactionalHandler(uow, controller.handle)
