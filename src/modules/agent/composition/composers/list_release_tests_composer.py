from modules.agent.application.use_cases import ListReleaseTestsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseTestRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_release_tests_controller import ListReleaseTestsController
from shared.infra.transactional_handler import TransactionalHandler


def list_release_tests_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentReleaseTestRepository(uow)
    use_case = ListReleaseTestsUseCase(repo)
    controller = ListReleaseTestsController(use_case)
    return TransactionalHandler(uow, controller.handle)
