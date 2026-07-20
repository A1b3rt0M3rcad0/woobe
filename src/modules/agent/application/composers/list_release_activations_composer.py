from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.list_release_activations import (
    ListAgentReleaseActivationsUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_release_activations_controller import (
    ListAgentReleaseActivationsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_release_activations_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = ListAgentReleaseActivationsUseCase(uow.release_activations)
    controller = ListAgentReleaseActivationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
