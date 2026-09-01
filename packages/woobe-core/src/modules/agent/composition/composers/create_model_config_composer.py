from modules.agent.application.use_cases import CreateModelConfigUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentModelConfigRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_model_config_controller import CreateModelConfigController
from shared.infra.transactional_handler import TransactionalHandler


def create_model_config_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentModelConfigRepository(uow)
    use_case = CreateModelConfigUseCase(repo)
    controller = CreateModelConfigController(use_case)
    return TransactionalHandler(uow, controller.handle)
