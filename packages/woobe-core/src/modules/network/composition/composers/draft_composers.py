from modules.agent.entrypoint import NetworkAgentAvailabilityReader
from modules.network.application.use_cases.draft_use_cases import SaveNetworkDraftUseCase
from modules.network.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.network.infra.database.draft_repository import (
    SQLAlchemyNetworkDraftRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.draft_controllers import (
    SaveNetworkDraftController,
)
from shared.infra.transactional_handler import TransactionalHandler


def save_network_draft_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkDraftRepository(uow)
    agent_availability = NetworkAgentAvailabilityReader()
    use_case = SaveNetworkDraftUseCase(
        repository,
        agent_availability,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
    )
    controller = SaveNetworkDraftController(use_case)
    return TransactionalHandler(uow, controller.handle)
