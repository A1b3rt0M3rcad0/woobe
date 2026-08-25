from modules.agent.application.use_cases import ListModelConfigsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_model_configs_controller import ListModelConfigsController
from shared.infra.transactional_handler import TransactionalHandler


def list_model_configs_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = ListModelConfigsUseCase(repo)
    controller = ListModelConfigsController(use_case)
    return TransactionalHandler(uow, controller.handle)
