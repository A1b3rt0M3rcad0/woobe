from modules.agent.application.use_cases.list_agent_runs import ListAgentRunsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, RUN_EVENT_JOURNAL
from modules.agent.infra.database.agent_run_repository import SQLAlchemyAgentRunRepository
from modules.agent.infra.database.project_access_repository import SQLAlchemyProjectAccessRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_agent_runs_controller import ListAgentRunsController
from shared.infra.transactional_handler import TransactionalHandler


def list_agent_runs_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    use_case = ListAgentRunsUseCase(
        SQLAlchemyAgentRunRepository(uow),
        SQLAlchemyProjectAccessRepository(uow),
        RUN_EVENT_JOURNAL,
    )
    controller = ListAgentRunsController(use_case)
    return TransactionalHandler(uow, controller.handle)
