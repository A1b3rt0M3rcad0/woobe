from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.infra.repositories import SQLAlchemyAskJobRepository
from modules.runtime.presentation.controllers.get_ask_job_controller import (
    GetAskJobController,
)
from modules.agent.application.use_cases.runtime_use_cases import GetAskJobUseCase


def get_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> GetAskJobController:
    repo = SQLAlchemyAskJobRepository(session_factory)
    use_case = GetAskJobUseCase(repo)
    return GetAskJobController(use_case)
