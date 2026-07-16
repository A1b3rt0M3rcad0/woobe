from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases import GetAskJobUseCase
from modules.agent.infra.database.repositories import SQLAlchemyAskJobRepository
from modules.agent.presentation.controllers.get_ask_job_controller import (
    GetAskJobController,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork


def get_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> GetAskJobController:
    repo = SQLAlchemyAskJobRepository(cast(UnitOfWork, session_factory))
    use_case = GetAskJobUseCase(repo)
    return GetAskJobController(use_case)
