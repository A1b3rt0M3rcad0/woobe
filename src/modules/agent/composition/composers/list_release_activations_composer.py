from modules.agent.application.use_cases.list_release_activations import (
    ListAgentReleaseActivationsUseCase,
)
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.release_activation_repository import (
    SQLAlchemyAgentReleaseActivationRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_release_activations_controller import (
    ListAgentReleaseActivationsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_release_activations_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentReleaseActivationRepository(uow)
    use_case = ListAgentReleaseActivationsUseCase(repo)
    controller = ListAgentReleaseActivationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
