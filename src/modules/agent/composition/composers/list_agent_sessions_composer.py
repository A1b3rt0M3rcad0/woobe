from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareListAgentSessionsUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.runtime_session_repository import SQLAlchemyRuntimeSessionRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_agent_sessions_controller import ListAgentSessionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_agent_sessions_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    session_repo = SQLAlchemyRuntimeSessionRepository(uow)
    use_case = EnvironmentAwareListAgentSessionsUseCase(session_repo)
    controller = ListAgentSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
