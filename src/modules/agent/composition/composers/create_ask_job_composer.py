from modules.agent.application.use_cases import CreateAskJobUseCase
from modules.agent.composition.resources import DATABASE_ENGINE, SESSION_FACTORY
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
    SQLAlchemyAskJobRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_ask_job_controller import (
    CreateAskJobController,
)
from modules.agent.runtime.runtime_environment_guard import AgentRuntimeEnvironmentGuard
from shared.infra.transactional_handler import TransactionalHandler


def create_ask_job_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAskJobRepository(uow)
    outbox = SQLAlchemyAgentOutboxEventWriter(uow)
    use_case = AgentRuntimeEnvironmentGuard(
        CreateAskJobUseCase(repo, outbox),
        SESSION_FACTORY,
        default_environment="production",
    )
    controller = CreateAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
