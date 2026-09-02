from modules.agent.application.use_cases.chat_surface_session import (
    CloseAgentChatSurfaceSessionUseCase,
    CreateAgentChatSurfaceSessionUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.chat_surface_session_repository import (
    SQLAlchemyAgentChatSurfaceSessionRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.chat_surface_session_controllers import (
    CloseAgentChatSurfaceSessionController,
    CreateAgentChatSurfaceSessionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_agent_chat_surface_session_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyAgentChatSurfaceSessionRepository(uow)
    use_case = CreateAgentChatSurfaceSessionUseCase(repository)
    controller = CreateAgentChatSurfaceSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)


def close_agent_chat_surface_session_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyAgentChatSurfaceSessionRepository(uow)
    use_case = CloseAgentChatSurfaceSessionUseCase(repository)
    controller = CloseAgentChatSurfaceSessionController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = [
    "close_agent_chat_surface_session_composer",
    "create_agent_chat_surface_session_composer",
]
