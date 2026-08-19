from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.composition.runtime.runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.database.database import AgentDatabase, agent_session_factory
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAskJobRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_ask_job_controller import (
    CreateAskJobController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_ask_job_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAskJobRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = AgentRuntimeEnvironmentGuard(
        CreateAskJobUseCase(repo, outbox),
        agent_session_factory(database),
        default_environment="production",
    )
    controller = CreateAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
