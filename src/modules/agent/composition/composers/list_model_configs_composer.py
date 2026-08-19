from modules.agent.application.use_cases import ListModelConfigsUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_model_configs_controller import ListModelConfigsController
from shared.infra.transactional_handler import TransactionalHandler


def list_model_configs_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = ListModelConfigsUseCase(repo)
    controller = ListModelConfigsController(use_case)
    return TransactionalHandler(uow, controller.handle)
