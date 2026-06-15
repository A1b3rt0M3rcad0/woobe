from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseTestRepository
from modules.agent.application.use_cases import ListReleaseTestsUseCase
from modules.agent.presentation.controllers.list_release_tests_controller import ListReleaseTestsController
from shared.application.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_release_tests_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseTestRepository(uow)
    use_case = ListReleaseTestsUseCase(repo)
    controller = ListReleaseTestsController(use_case)
    return TransactionalHandler(uow, controller.handle)
