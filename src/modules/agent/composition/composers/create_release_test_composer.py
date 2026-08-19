from modules.agent.application.use_cases import CreateReleaseTestUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseTestRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_release_test_controller import CreateReleaseTestController
from shared.infra.transactional_handler import TransactionalHandler


def create_release_test_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentReleaseTestRepository(uow)
    use_case = CreateReleaseTestUseCase(repo)
    controller = CreateReleaseTestController(use_case)
    return TransactionalHandler(uow, controller.handle)
