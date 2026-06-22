from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.promote_release_controller import (
    PromoteReleaseController,
)
from shared.infra.transactional_handler import TransactionalHandler


def promote_release_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = AutoCompatibleReleaseLifecycleUseCase(repo)
    controller = PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
