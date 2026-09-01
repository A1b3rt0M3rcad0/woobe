from modules.agent.application.use_cases import GetAskJobUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAskJobRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_ask_job_controller import GetAskJobController
from shared.infra.transactional_handler import TransactionalHandler


def get_ask_job_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAskJobRepository(uow)
    use_case = GetAskJobUseCase(repo)
    controller = GetAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
