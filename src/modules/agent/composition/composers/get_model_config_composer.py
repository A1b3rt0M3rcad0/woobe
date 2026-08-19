from modules.agent.application.use_cases import GetModelConfigUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_model_config_controller import GetModelConfigController
from shared.infra.transactional_handler import TransactionalHandler


def get_model_config_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = GetModelConfigUseCase(repo)
    controller = GetModelConfigController(use_case)
    return TransactionalHandler(uow, controller.handle)
