from __future__ import annotations

from modules.agent.application.use_cases.read_agent_run_context import (
    ReadAgentRunContextUseCase,
)
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.project_access_repository import (
    SQLAlchemyProjectAccessRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.agent_run_context_controller import (
    AgentRunContextController,
)
from shared.infra.transactional_handler import TransactionalHandler


def agent_run_context_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    run_repository = SQLAlchemyAgentRunRepository(uow)
    project_access_repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ReadAgentRunContextUseCase(
        run_repository,
        project_access_repository,
    )
    controller = AgentRunContextController(use_case)
    return TransactionalHandler(uow, controller.handle_by_run)


def agent_run_context_by_trace_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    run_repository = SQLAlchemyAgentRunRepository(uow)
    project_access_repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ReadAgentRunContextUseCase(
        run_repository,
        project_access_repository,
    )
    controller = AgentRunContextController(use_case)
    return TransactionalHandler(uow, controller.handle_by_trace)


def agent_run_detail_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    run_repository = SQLAlchemyAgentRunRepository(uow)
    project_access_repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ReadAgentRunContextUseCase(
        run_repository,
        project_access_repository,
    )
    controller = AgentRunContextController(use_case)
    return TransactionalHandler(uow, controller.handle_detail_by_run)


def agent_run_detail_by_trace_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    run_repository = SQLAlchemyAgentRunRepository(uow)
    project_access_repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ReadAgentRunContextUseCase(
        run_repository,
        project_access_repository,
    )
    controller = AgentRunContextController(use_case)
    return TransactionalHandler(uow, controller.handle_detail_by_trace)

