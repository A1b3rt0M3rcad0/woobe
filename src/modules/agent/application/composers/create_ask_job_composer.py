from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.presentation.controllers.create_ask_job_controller import (
    CreateAskJobController,
)
from modules.agent.application.use_cases import CreateAskJobUseCase
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = uow.ask_jobs
    session_repo = uow.sessions
    use_case = CreateAskJobUseCase(repo, session_repo)
    controller = CreateAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
