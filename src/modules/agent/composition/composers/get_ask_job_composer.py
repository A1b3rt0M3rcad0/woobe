from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import GetAskJobUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_ask_job_controller import (
    GetAskJobController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = GetAskJobUseCase(uow.ask_jobs)
    controller = GetAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
